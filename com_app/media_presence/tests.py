from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import SocialMediaContent
from .sync_services import _facebook_posts, _normalise, _save_post, _youtube_posts, sync_provider


class SocialMediaSyncTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="social-user", password="test-password")
        self.client.force_login(self.user)

    @override_settings(SOCIAL_MEDIA_API_CONFIG={"facebook": {"page_id": "1", "access_token": "token"}})
    @patch("com_app.media_presence.sync_services._request_json", return_value={"data": None})
    def test_facebook_missing_data_is_treated_as_empty(self, request_json):
        self.assertEqual(_facebook_posts(), [])

    @override_settings(SOCIAL_MEDIA_API_CONFIG={"youtube": {"api_key": " key ", "channel_id": " channel "}})
    @patch("com_app.media_presence.sync_services._request_json")
    def test_youtube_strips_credentials_and_channel_id(self, request_json):
        request_json.return_value = {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "uploads"}}}]}
        request_json.side_effect = [
            {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "uploads"}}}]},
            {"items": []},
        ]
        self.assertEqual(_youtube_posts(), [])
        first_params = request_json.call_args_list[0].kwargs["params"]
        self.assertEqual(first_params["key"], "key")
        self.assertEqual(first_params["id"], "channel")

    def test_normalise_twitter_post_maps_weekly_tracker_fields(self):
        post = _normalise("twitter", {"id": "123", "text": "A new impact story", "created_at": "2026-09-25T08:30:00Z"})
        self.assertEqual(post["identifier"], "123")
        self.assertEqual(post["url"], "https://x.com/i/status/123")
        self.assertEqual(post["published_at"].tzinfo, dt_timezone.utc)

    def test_normalise_youtube_post_maps_statistics(self):
        post = _normalise("youtube", {
            "id": "video-item", "contentDetails": {"videoId": "video-1"},
            "snippet": {"title": "Video", "description": "Description", "publishedAt": "2026-09-25T08:30:00Z"},
            "statistics": {"viewCount": "42", "likeCount": "7", "commentCount": "3"},
        })
        self.assertEqual(post["views_count"], 42)
        self.assertEqual(post["likes_count"], 7)
        self.assertEqual(post["comments_count"], 3)

    def test_upsert_is_idempotent(self):
        post = {
            "identifier": "abc", "title": "Post", "content": "Copy", "url": "https://x.com/i/status/abc",
            "published_at": datetime(2026, 9, 25, 8, 30, tzinfo=dt_timezone.utc),
            "media_visual_type": "Graphics", "raw": {"id": "abc"},
        }
        self.assertTrue(_save_post("twitter", post))
        self.assertFalse(_save_post("twitter", post))
        self.assertEqual(SocialMediaContent.objects.filter(source_key="twitter:abc").count(), 1)

    @override_settings(
        SOCIAL_MEDIA_SYNC_ENABLED=True,
        SOCIAL_MEDIA_API_CONFIG={"twitter": {"enabled": True, "account_id": "1", "access_token": "token"}},
    )
    @patch("com_app.media_presence.sync_services.PROVIDERS", {"twitter": lambda: [{"id": "1", "text": "hello", "created_at": "2026-09-25T08:30:00Z"}]})
    def test_provider_sync_reports_created_post(self):
        result = sync_provider("twitter")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["created"], 1)
        self.assertTrue(SocialMediaContent.objects.filter(source_key="twitter:1").exists())

    @patch("com_app.media_presence.views.sync_provider")
    def test_platform_sync_button_runs_only_selected_provider(self, sync):
        sync.return_value = {"status": "ok", "fetched": 2, "created": 1, "updated": 1}
        response = self.client.post(reverse("media_presence:social_media_sync_provider", args=["youtube"]))
        self.assertRedirects(response, reverse("media_presence:social_media"))
        sync.assert_called_once_with("youtube")
