from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, HttpResponse
import csv
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.db.models import Count
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView

from .forms import BroadcastForm, GalleryForm, GalleryPhotoForm, SocialMediaContentForm, NewsletterForm
from .models import Broadcast, GalleryPhoto, PhotoGallery, SocialMediaContent, SocialMediaSyncState, Newsletter
from .sync_services import PROVIDERS, sync_provider


class BroadcastListView(LoginRequiredMixin, ListView):
    model = Broadcast
    template_name = "media_presence/broadcast_list.html"
    context_object_name = "broadcasts"

    def get_queryset(self):
        return Broadcast.objects.filter(is_published=True)


class BroadcastCreateView(LoginRequiredMixin, CreateView):
    model = Broadcast
    form_class = BroadcastForm
    template_name = "media_presence/broadcast_form.html"
    success_url = reverse_lazy("media_presence:broadcasts")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Broadcast appearance saved.")
        return super().form_valid(form)


class GalleryListView(LoginRequiredMixin, ListView):
    model = PhotoGallery
    template_name = "media_presence/gallery_list.html"
    context_object_name = "galleries"

    def get_queryset(self):
        return PhotoGallery.objects.filter(published=True).select_related("project").prefetch_related("photos")


class GalleryCreateView(LoginRequiredMixin, CreateView):
    model = PhotoGallery
    form_class = GalleryForm
    template_name = "media_presence/gallery_form.html"
    success_url = reverse_lazy("media_presence:galleries")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Photo gallery created.")
        return response


def gallery_detail(request, pk):
    gallery = get_object_or_404(PhotoGallery.objects.select_related("project").prefetch_related("photos"), pk=pk, published=True)
    if request.method == "POST":
        form = GalleryPhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.gallery = gallery
            photo.save()
            messages.success(request, "Photo added to gallery.")
            return redirect("media_presence:gallery_detail", pk=gallery.pk)
    else:
        form = GalleryPhotoForm()
    return render(request, "media_presence/gallery_detail.html", {
        "gallery": gallery,
        "form": form,
        "back_url": reverse_lazy("media_presence:gallery_activities", kwargs={
            "year": gallery.year, "quarter": gallery.quarter, "project_id": gallery.project_id,
        }),
    })


@login_required
def photo_download(request, pk):
    photo = get_object_or_404(
        GalleryPhoto.objects.select_related("gallery"),
        pk=pk,
        gallery__published=True,
    )
    return redirect(photo.display_url)


@login_required
def gallery_years(request):
    items = PhotoGallery.objects.filter(published=True).values("year").annotate(
        activity_count=Count("id", distinct=True),
        photo_count=Count("photos", distinct=True),
    ).order_by("-year")
    return render(request, "media_presence/gallery_browse.html", {
        "level": "years", "items": items, "heading": "Years", "subheading": "Choose a year to explore the documentation archive.",
    })


@login_required
def gallery_quarters(request, year):
    items = PhotoGallery.objects.filter(published=True, year=year).values("quarter").annotate(
        activity_count=Count("id", distinct=True), photo_count=Count("photos", distinct=True),
    ).order_by("quarter")
    return render(request, "media_presence/gallery_browse.html", {
        "level": "quarters", "items": items, "year": year, "heading": f"{year} quarters", "subheading": "Choose a quarter.",
    })


@login_required
def gallery_projects(request, year, quarter):
    items = PhotoGallery.objects.filter(published=True, year=year, quarter=quarter).values(
        "project_id", "project__name"
    ).annotate(activity_count=Count("id", distinct=True), photo_count=Count("photos", distinct=True)).order_by("project__name")
    return render(request, "media_presence/gallery_browse.html", {
        "level": "projects", "items": items, "year": year, "quarter": quarter,
        "heading": f"{year} · Q{quarter} projects", "subheading": "Choose a project.",
    })


@login_required
def gallery_activities(request, year, quarter, project_id):
    items = PhotoGallery.objects.filter(
        published=True, year=year, quarter=quarter, project_id=project_id,
    ).select_related("project").annotate(photo_count=Count("photos", distinct=True)).order_by("year")
    project = items.first().project if items else get_object_or_404(PhotoGallery, year=year, quarter=quarter, project_id=project_id, published=True).project
    return render(request, "media_presence/gallery_browse.html", {
        "level": "activities", "items": items, "year": year, "quarter": quarter,
        "project": project, "heading": f"{project.name} activities", "subheading": "Choose an activity to view its photos.",
    })


class SocialMediaListView(LoginRequiredMixin, ListView):
    model = SocialMediaContent
    template_name = "media_presence/social_media_list.html"
    context_object_name = "social_posts"

    def get_queryset(self):
        queryset = super().get_queryset().order_by("-published_at", "-created_at")
        status = self.request.GET.get("status")
        platform = self.request.GET.get("platform")
        if status:
            queryset = queryset.filter(tracking_status=status)
        if platform:
            queryset = queryset.filter(platform=platform)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        provider_labels = dict(SocialMediaContent.PLATFORM_CHOICES)
        provider_keys = tuple(PROVIDERS.keys())
        states = {
            state.provider: state
            for state in SocialMediaSyncState.objects.filter(provider__in=provider_keys)
        }
        context["social_providers"] = [
            {
                "key": provider,
                "label": provider_labels.get(provider, provider.title()),
                "enabled": getattr(settings, "SOCIAL_MEDIA_API_CONFIG", {}).get(provider, {}).get("enabled", False),
                "state": states.get(provider),
            }
            for provider in provider_keys
        ]
        return context


@login_required
@require_POST
def sync_social_media_provider(request, provider):
    """Fetch and save content for one platform from the content page."""
    if provider not in PROVIDERS:
        messages.error(request, "That social media platform is not supported.")
        return redirect("media_presence:social_media")

    result = sync_provider(provider)
    label = dict(SocialMediaContent.PLATFORM_CHOICES).get(provider, provider.title())
    if result["status"] == "ok":
        messages.success(
            request,
            f"{label} synced: {result['fetched']} fetched, {result['created']} new, "
            f"{result['updated']} updated.",
        )
    elif result["status"] == "disabled":
        messages.warning(
            request,
            f"{label} sync is disabled. Enable its provider setting and configure valid credentials.",
        )
    else:
        messages.error(request, f"{label} sync failed: {result.get('error', 'Unknown error')}")
    return redirect("media_presence:social_media")


@login_required
def export_social_media_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="social-media-tracker.csv"'
    writer = csv.writer(response)
    writer.writerow(["Sno", "Week #", "Date", "Time (GMT)", "Post Status", "Post Copy", "Post Topic/Type", "Post X link", "Project", "Media/Visual Type", "Views", "Likes", "Dislikes", "Comments", "Shares"])
    for index, post in enumerate(SocialMediaContent.objects.all().order_by("-published_at"), start=1):
        local_date = timezone.localtime(post.published_at) if post.published_at else None
        writer.writerow([index, post.week_number, local_date.date() if local_date else "", local_date.strftime("%H:%M") if local_date else "", post.get_tracking_status_display(), post.content, post.topic_type, post.url, post.project, post.media_visual_type, post.views_count, post.likes_count, post.dislikes_count, post.comments_count, post.shares_count])
    return response


@login_required
def export_social_media_excel(request):
    from openpyxl import Workbook
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Social Media Tracker"
    sheet.append(["Sno", "Week #", "Date", "Time (GMT)", "Post Status", "Post Copy", "Post Topic/Type", "Post X link", "Project", "Media/Visual Type", "Views", "Likes", "Dislikes", "Comments", "Shares"])
    for index, post in enumerate(SocialMediaContent.objects.all().order_by("-published_at"), start=1):
        local_date = timezone.localtime(post.published_at) if post.published_at else None
        sheet.append([index, post.week_number, local_date.date() if local_date else None, local_date.strftime("%H:%M") if local_date else None, post.get_tracking_status_display(), post.content, post.topic_type, post.url, post.project, post.media_visual_type, post.views_count, post.likes_count, post.dislikes_count, post.comments_count, post.shares_count])
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="social-media-tracker.xlsx"'
    workbook.save(response)
    return response


class SocialMediaCreateView(LoginRequiredMixin, CreateView):
    model = SocialMediaContent
    form_class = SocialMediaContentForm
    template_name = "media_presence/social_media_form.html"
    success_url = reverse_lazy("media_presence:social_media")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Social media content saved.")
        return super().form_valid(form)


class NewsletterListView(LoginRequiredMixin, ListView):
    model = Newsletter
    template_name = "media_presence/newsletter_list.html"
    context_object_name = "newsletters"


class NewsletterCreateView(LoginRequiredMixin, CreateView):
    model = Newsletter
    form_class = NewsletterForm
    template_name = "media_presence/newsletter_form.html"
    success_url = reverse_lazy("media_presence:newsletters")

    def form_valid(self, form):
        messages.success(self.request, "Newsletter uploaded.")
        return super().form_valid(form)
