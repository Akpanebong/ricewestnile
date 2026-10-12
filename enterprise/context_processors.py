from .system_catalog import can_view_governance, visible_systems
from django.utils import timezone
from django.urls import reverse


SOCIAL_MEDIA_LINKS = (
    {"label": "Twitter / X", "url": "https://x.com/RICEWestNile", "icon": "fa-brands fa-x-twitter"},
    {"label": "WhatsApp", "url": "https://chat.whatsapp.com/DQAsWKcPRvb0aGZNAYYhZK", "icon": "fa-brands fa-whatsapp"},
    {"label": "Facebook", "url": "https://www.facebook.com/profile.php?id=100068996303410", "icon": "fa-brands fa-facebook"},
    {"label": "Facebook Page", "url": "https://www.facebook.com/ricewestnile/", "icon": "fa-brands fa-facebook"},
    {"label": "LinkedIn", "url": "https://www.linkedin.com/in/rice-west-nile-411064181/", "icon": "fa-brands fa-linkedin"},
    {"label": "Instagram", "url": "https://www.instagram.com/ricewestnile", "icon": "fa-brands fa-instagram"},
    {"label": "YouTube", "url": "https://www.youtube.com/@ricewestnile481", "icon": "fa-brands fa-youtube"},
)


def system_catalog(request):
    return {"enterprise_systems": visible_systems(request.user), "social_media_links": SOCIAL_MEDIA_LINKS}


def active_system_ui(request):
    namespace = getattr(getattr(request, "resolver_match", None), "namespace", "") or ""
    path = getattr(request, "path", "") or ""

    if namespace == "comm" or path.startswith("/communication/"):
        base_template = "communication/base.html"
    elif namespace == "mne_core" or path.startswith("/mne/"):
        base_template = "mne/base.html"
    elif namespace == "procurement_core" or path.startswith("/procurement/"):
        base_template = "procurement/base.html"
    elif path.startswith("/asset/"):
        base_template = "asset/base.html"
    elif namespace == "garcis" or path.startswith("/garcis/"):
        base_template = "garcis/base.html"
    elif path.startswith("/governance/"):
        base_template = "governance/base.html"
    else:
        base_template = "base.html"

    core_namespace = namespace if namespace in {"mne_core", "procurement_core"} else "mne_core"
    return {
        "governance_visible": can_view_governance(getattr(request, "user", None)),
        "active_base_template": base_template,
        "core_url_namespace": core_namespace,
        "governance_can_manage": bool(
            getattr(request, "user", None)
            and request.user.is_authenticated
            and (request.user.is_superuser or request.user.groups.filter(name__iexact="ED").exists())
        ),
        "governance_can_create": bool(
            getattr(request, "user", None)
            and request.user.is_authenticated
            and (
                request.user.is_superuser
                or request.user.groups.filter(name__iexact="ED").exists()
                or request.user.groups.filter(name__iexact="Governance").exists()
            )
        ),
    }


def forum_activity(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"unread_forum_count": 0, "unread_forum_items": []}

    from hr_apps.HRapp.models import ForumPost, ForumThread

    last_seen = request.user.forum_last_seen_at
    if last_seen is None:
        # Establish a baseline for existing content. Future threads/replies
        # will then be treated as unread without notifying everyone about the
        # entire historical archive on first login.
        request.user.__class__.objects.filter(pk=request.user.pk, forum_last_seen_at__isnull=True).update(
            forum_last_seen_at=timezone.now()
        )
        return {"unread_forum_count": 0, "unread_forum_items": []}

    new_threads = ForumThread.objects.filter(created_at__gt=last_seen).exclude(author=request.user)
    new_posts = ForumPost.objects.filter(created_at__gt=last_seen).exclude(author=request.user).select_related("thread")
    items = [
        {"title": f"New thread: {thread.title}", "url": reverse("forum_detail", kwargs={"thread_id": thread.pk}), "created_at": thread.created_at}
        for thread in new_threads.order_by("-created_at")[:5]
    ]
    items += [
        {"title": f"New reply in: {post.thread.title}", "url": reverse("forum_detail", kwargs={"thread_id": post.thread.pk}), "created_at": post.created_at}
        for post in new_posts.order_by("-created_at")[:5]
    ]
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return {
        "unread_forum_count": new_threads.count() + new_posts.count(),
        "unread_forum_items": items[:5],
    }
