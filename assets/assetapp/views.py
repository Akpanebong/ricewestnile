from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy

from .models import Asset
from .forms import AssetForm
from .utils import export_assets_to_excel
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Asset, AssetMaintenance, AuditLog
from .utils import get_client_ip


from django.db.models import Sum, Count
from django.utils.timezone import now
from datetime import timedelta

from .models import Asset, AssetMaintenance, AuditLog


def dashboard(request):
    today = now().date()
    upcoming_threshold = today + timedelta(days=30)

    context = {
        # KPIs
        "total_assets": Asset.objects.count(),
        "total_asset_value": Asset.objects.aggregate(
            total=Sum("purchase_value")
        )["total"] or 0,

        "total_depreciation": Asset.objects.aggregate(
            total=Sum("depreciation_accumulated")
        )["total"] or 0,

        "total_net_value": sum(
            a.net_book_value for a in Asset.objects.all()
        ),

        "allocated_assets": Asset.objects.filter(allocation__isnull=False).count(),
        "unallocated_assets": Asset.objects.filter(allocation__isnull=True).count(),

        # Groupings
        "assets_by_category": (
            Asset.objects.values("category")
            .annotate(count=Count("id"))
        ),

        "assets_by_acquisition": (
            Asset.objects.values("mode_of_acquisition")
            .annotate(count=Count("id"))
        ),

        # Maintenance
        "upcoming_maintenance": AssetMaintenance.objects.filter(
            next_due_date__lte=upcoming_threshold,
            next_due_date__gte=today,
        ).select_related("asset"),

        "overdue_maintenance": AssetMaintenance.objects.filter(
            next_due_date__lt=today
        ).select_related("asset"),

        # Activity feeds
        "recent_assets": Asset.objects.order_by("-created_at")[:5],
        "recent_maintenances": AssetMaintenance.objects.order_by("-recorded_at")[:5],
        "recent_logs": AuditLog.objects.order_by("-timestamp")[:5],
    }

    return render(request, "assets/dashboard.html", context)


def asset_list(request):
    assets = Asset.objects.all()

    start = request.GET.get('start')
    end = request.GET.get('end')

    if start and end:
        assets = assets.filter(date_of_entry__range=[start, end])

    if 'export' in request.GET:
        return export_assets_to_excel(assets)

    return render(request, 'assets/asset_list.html', {'assets': assets})


def asset_create(request):
    form = AssetForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('asset:asset_list')
    return render(request, 'assets/asset_form.html', {'form': form})


def asset_detail(request, pk, slug):
    asset = get_object_or_404(Asset, pk=pk, slug=slug)
    return render(request, 'assets/asset_detail.html', {'asset': asset})


@login_required
def add_maintenance(request, pk, slug):
    asset = get_object_or_404(Asset, pk=pk, slug=slug)

    if request.method == "POST":
        maintenance_date = request.POST.get("maintenance_date")
        maintenance_type = request.POST.get("maintenance_type")
        cost = request.POST.get("cost") or 0
        description = request.POST.get("description")
        next_due_date = request.POST.get("next_due_date")

        if not maintenance_date or not maintenance_type:
            messages.error(request, "Maintenance date and type are required.")
            return redirect(reverse_lazy("asset:add_maintenance", kwargs={'pk': asset.id, 'slug': asset.slug}))

        maintenance = AssetMaintenance.objects.create(
            asset=asset,
            maintenance_date=maintenance_date,
            maintenance_type=maintenance_type,
            cost=cost,
            description=description,
            next_due_date=next_due_date or None,
        )

        # AUDIT LOG
        AuditLog.objects.create(
            user=request.user,
            action="MAINTENANCE",
            model_name="AssetMaintenance",
            object_id=maintenance.id,
            description=f"Maintenance added for asset {asset.asset_no}",
            ip_address=get_client_ip(request),
        )

        messages.success(request, "Maintenance record added successfully.")
        return redirect(reverse_lazy("asset:asset_detail", kwargs={'pk': asset.id, 'slug': asset.slug}))

    return render(
        request,
        "asset/add_maintenance.html",
        {"asset": asset},
    )
