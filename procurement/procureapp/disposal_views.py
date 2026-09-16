from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from assets.assetapp.models import AssetDisposalRequest


@login_required
def disposal_queue(request):
    disposals = AssetDisposalRequest.objects.select_related("asset", "declared_by", "reviewed_by")
    return render(request, "procurement/disposal_queue.html", {"disposals": disposals})


@login_required
def disposal_review(request, pk):
    disposal = get_object_or_404(AssetDisposalRequest, pk=pk)
    if request.method == "POST":
        status = request.POST.get("status")
        if status in dict(AssetDisposalRequest.Status.choices):
            disposal.status = status
            disposal.procurement_notes = request.POST.get("procurement_notes", "")
            disposal.reviewed_by = request.user
            disposal.reviewed_at = timezone.now()
            disposal.save(update_fields=["status", "procurement_notes", "reviewed_by", "reviewed_at"])
            messages.success(request, "Disposal request updated.")
    return redirect("disposal_queue")
