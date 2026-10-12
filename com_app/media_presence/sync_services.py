import base64
import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import SocialMediaContent, SocialMediaSyncState


class SocialMediaSyncError(Exception):
    """A provider request or response could not be processed."""


def _config(provider):
    return getattr(settings, "SOCIAL_MEDIA_API_CONFIG", {}).get(provider, {})


def _request_json(url, *, params=None, headers=None):
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"Accept": "application/json", **(headers or {})})
    try:
        with urlopen(request, timeout=getattr(settings, "SOCIAL_MEDIA_API_TIMEOUT_SECONDS", 30)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = ""
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            error = error_payload.get("error", error_payload) if isinstance(error_payload, dict) else error_payload
            detail = error.get("message", "") if isinstance(error, dict) else str(error)
        except (UnicodeDecodeError, ValueError):
            pass
        if exc.code == 402 and "api.x.com" in url:
            raise SocialMediaSyncError(
                "X API access is not included in the current account plan (HTTP 402). "
                "Upgrade the plan or set SOCIAL_TWITTER_ENABLED=False."
            ) from exc
        suffix = f": {detail}" if detail else ""
        raise SocialMediaSyncError(
            f"Request failed for {url.split('?')[0]}: HTTP {exc.code}{suffix}"
        ) from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise SocialMediaSyncError(f"Request failed for {url.split('?')[0]}: {exc}") from exc
    if isinstance(payload, dict) and payload.get("error"):
        error = payload["error"]
        message = error.get("message", error) if isinstance(error, dict) else error
        raise SocialMediaSyncError(str(message))
    return payload


def _parse_datetime(value):
    if not value:
        return timezone.now()
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return timezone.now()
    return timezone.make_aware(parsed) if parsed.tzinfo is None else parsed


def _media_type(value):
    value = (value or "").lower()
    if value in {"video", "animated_gif", "youtube"}:
        return "Video/Clip"
    if value in {"photo", "image", "picture"}:
        return "Graphics"
    if value:
        return value.replace("_", " ").title()
    return ""


def _week_label(published_at):
    return f"Week {published_at.isocalendar().week}"


def _facebook_posts():
    config = _config("facebook")
    if not config.get("page_id") or not config.get("access_token"):
        raise SocialMediaSyncError("Facebook requires page_id and access_token.")
    return _request_json(
        f"https://graph.facebook.com/{config.get('api_version', 'v22.0')}/{config['page_id']}/posts",
        params={
            "fields": "id,message,created_time,permalink_url,attachments{media_type,type,url},likes.summary(true),comments.summary(true),shares",
            "limit": 100,
            "access_token": config["access_token"].strip(),
        },
    ).get("data") or []


def _youtube_posts():
    config = _config("youtube")
    api_key = str(config.get("api_key") or "").strip()
    channel_id = str(config.get("channel_id") or "").strip()
    if not api_key or not channel_id:
        raise SocialMediaSyncError("YouTube requires api_key and channel_id.")
    base = "https://www.googleapis.com/youtube/v3"
    channel = _request_json(
        f"{base}/channels",
        params={"part": "contentDetails", "id": channel_id, "key": api_key},
    ).get("items", [])
    if not channel:
        raise SocialMediaSyncError("YouTube channel was not found or is not accessible.")
    uploads = channel[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not uploads:
        return []
    items = _request_json(
        f"{base}/playlistItems",
        params={
            "part": "snippet,contentDetails",
            "playlistId": uploads,
            "maxResults": 50,
            "key": api_key,
        },
    ).get("items", [])
    video_ids = [item.get("contentDetails", {}).get("videoId") for item in items]
    video_ids = [video_id for video_id in video_ids if video_id]
    if video_ids:
        stats = _request_json(
            f"{base}/videos",
            params={"part": "statistics", "id": ",".join(video_ids), "key": api_key},
        ).get("items", [])
        stats_by_id = {item.get("id"): item.get("statistics", {}) for item in stats}
        for item in items:
            video_id = item.get("contentDetails", {}).get("videoId")
            item["statistics"] = stats_by_id.get(video_id, {})
    return items


def _twitter_posts():
    config = _config("twitter")
    bearer = config.get("bearer_token")
    if not bearer and config.get("api_key") and config.get("api_secret"):
        credentials = f"{config['api_key'].strip()}:{config['api_secret'].strip()}".encode("utf-8")
        request = Request(
            "https://api.twitter.com/oauth2/token",
            data=b"grant_type=client_credentials",
            method="POST",
            headers={
                "Authorization": f"Basic {base64.b64encode(credentials).decode('ascii')}",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
        )
        try:
            with urlopen(request, timeout=getattr(settings, "SOCIAL_MEDIA_API_TIMEOUT_SECONDS", 30)) as response:
                bearer = json.loads(response.read().decode("utf-8")).get("access_token")
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise SocialMediaSyncError(f"Twitter/X bearer-token request failed: {exc}") from exc
    bearer = bearer or config.get("access_token")
    if not config.get("account_id") or not bearer:
        raise SocialMediaSyncError("Twitter/X requires account_id and bearer_token or access_token.")
    return _request_json(
        f"https://api.x.com/2/users/{config['account_id']}/tweets",
        params={
            "max_results": 100,
            "tweet.fields": "created_at,text,attachments,entities,public_metrics",
            "expansions": "attachments.media_keys",
            "media.fields": "type,url,preview_image_url",
        },
        headers={"Authorization": f"Bearer {bearer.strip()}"},
    ).get("data", [])


def _normalise(provider, item):
    if provider == "facebook":
        identifier = item.get("id")
        content = item.get("message", "")
        published_at = _parse_datetime(item.get("created_time"))
        attachments = (item.get("attachments") or {}).get("data", [])
        visual = _media_type(attachments[0].get("media_type") if attachments else "")
        return {
            "identifier": identifier, "title": (content.splitlines()[0] if content else f"Facebook post {identifier}")[:255],
            "content": content, "url": item.get("permalink_url", ""), "published_at": published_at,
            "media_visual_type": visual, "views_count": None,
            "likes_count": ((item.get("likes") or {}).get("summary") or {}).get("total_count"),
            "dislikes_count": None,
            "comments_count": ((item.get("comments") or {}).get("summary") or {}).get("total_count"),
            "shares_count": (item.get("shares") or {}).get("count"), "raw": item,
        }
    if provider == "youtube":
        snippet = item.get("snippet", {})
        identifier = item.get("contentDetails", {}).get("videoId") or item.get("id", {}).get("videoId")
        content = snippet.get("description", "")
        statistics = item.get("statistics", {})
        return {
            "identifier": identifier, "title": snippet.get("title", f"YouTube video {identifier}")[:255],
            "content": content, "url": f"https://www.youtube.com/watch?v={identifier}",
            "published_at": _parse_datetime(snippet.get("publishedAt")), "media_visual_type": "Video/Clip",
            "views_count": _integer(statistics.get("viewCount")), "likes_count": _integer(statistics.get("likeCount")),
            "dislikes_count": _integer(statistics.get("dislikeCount")), "comments_count": _integer(statistics.get("commentCount")),
            "shares_count": None, "raw": item,
        }
    identifier = item.get("id")
    content = item.get("text", "")
    metrics = item.get("public_metrics", {})
    return {
        "identifier": identifier, "title": (content.splitlines()[0] if content else f"Twitter/X post {identifier}")[:255],
        "content": content, "url": f"https://x.com/i/status/{identifier}",
        "published_at": _parse_datetime(item.get("created_at")),
        "media_visual_type": _media_type((item.get("attachments") or {}).get("media_keys") and "image"),
        "views_count": metrics.get("impression_count"), "likes_count": metrics.get("like_count"),
        "dislikes_count": None, "comments_count": metrics.get("reply_count"),
        "shares_count": metrics.get("retweet_count"), "raw": item,
    }


def _integer(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@transaction.atomic
def _save_post(provider, post):
    source_key = f"{provider}:{post['identifier']}"
    obj, created = SocialMediaContent.objects.get_or_create(
        source_key=source_key,
        defaults={
            "platform": provider, "title": post["title"], "content": post["content"], "url": post["url"],
            "published_at": post["published_at"], "tracking_status": "posted", "post_identifier": post["identifier"],
            "week_number": _week_label(post["published_at"]), "media_visual_type": post["media_visual_type"],
            "views_count": post.get("views_count"), "likes_count": post.get("likes_count"),
            "dislikes_count": post.get("dislikes_count"), "comments_count": post.get("comments_count"),
            "shares_count": post.get("shares_count"), "metrics_synced_at": timezone.now(),
            "source_data": post["raw"], "last_synced_at": timezone.now(),
        },
    )
    if not created:
        obj.title = post["title"]
        obj.content = post["content"]
        obj.url = post["url"]
        obj.published_at = post["published_at"]
        obj.tracking_status = "posted"
        obj.post_identifier = post["identifier"]
        obj.week_number = _week_label(post["published_at"])
        if not obj.media_visual_type:
            obj.media_visual_type = post["media_visual_type"]
        obj.views_count = post.get("views_count")
        obj.likes_count = post.get("likes_count")
        obj.dislikes_count = post.get("dislikes_count")
        obj.comments_count = post.get("comments_count")
        obj.shares_count = post.get("shares_count")
        obj.metrics_synced_at = timezone.now()
        obj.source_data = post["raw"]
        obj.last_synced_at = timezone.now()
        obj.save(update_fields=("title", "content", "url", "published_at", "tracking_status", "post_identifier", "week_number", "media_visual_type", "views_count", "likes_count", "dislikes_count", "comments_count", "shares_count", "metrics_synced_at", "source_data", "last_synced_at"))
    return created


PROVIDERS = {"facebook": _facebook_posts, "youtube": _youtube_posts, "twitter": _twitter_posts}


def sync_provider(provider, *, force=False):
    config = _config(provider)
    if not force and not config.get("enabled", False):
        return {"provider": provider, "status": "disabled", "fetched": 0, "created": 0, "updated": 0}
    state, _ = SocialMediaSyncState.objects.get_or_create(provider=provider)
    state.last_started_at = timezone.now()
    state.last_error = ""
    state.save(update_fields=("last_started_at", "last_error"))
    try:
        normalised_posts = [_normalise(provider, item) for item in PROVIDERS[provider]()]
        normalised_posts = [post for post in normalised_posts if post.get("identifier")]
        created = sum(_save_post(provider, post) for post in normalised_posts)
        updated = len(normalised_posts) - created
        state.last_success_at = timezone.now()
        state.posts_fetched = len(normalised_posts)
        state.posts_created = created
        state.posts_updated = updated
        state.last_error = ""
        state.save(update_fields=("last_success_at", "posts_fetched", "posts_created", "posts_updated", "last_error"))
        return {"provider": provider, "status": "ok", "fetched": len(normalised_posts), "created": created, "updated": updated}
    except Exception as exc:
        state.last_error = str(exc)[:2000]
        state.save(update_fields=("last_error",))
        return {"provider": provider, "status": "error", "fetched": 0, "created": 0, "updated": 0, "error": str(exc)}


def sync_all(*, force=False):
    configured_providers = [
        provider for provider in PROVIDERS
        if _config(provider).get("enabled", False)
    ]
    # Provider-level enablement is sufficient for an explicit/manual sync. The
    # global switch still disables the command when no provider is enabled.
    # This avoids making a correctly configured YouTube provider require
    # --force just because the legacy global flag was left false.
    if not force and not getattr(settings, "SOCIAL_MEDIA_SYNC_ENABLED", False) and not configured_providers:
        return [{"provider": "all", "status": "disabled", "fetched": 0, "created": 0, "updated": 0}]
    return [sync_provider(provider, force=force) for provider in (PROVIDERS if force else configured_providers)]
