from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView

from .forms import BroadcastForm, GalleryForm, GalleryPhotoForm
from .models import Broadcast, GalleryPhoto, PhotoGallery


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
    return render(request, "media_presence/gallery_detail.html", {"gallery": gallery, "form": form})


@login_required
def photo_download(request, pk):
    photo = get_object_or_404(
        GalleryPhoto.objects.select_related("gallery"),
        pk=pk,
        gallery__published=True,
    )
    filename = photo.image.name.rsplit("/", 1)[-1]
    return FileResponse(photo.image.open("rb"), as_attachment=True, filename=filename)
