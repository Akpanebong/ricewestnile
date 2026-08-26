from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from .views import system_home


urlpatterns = [
    path("admin/", admin.site.urls),
    path("systems/", system_home, name="system_home"),
    path("asset/", include("assets.assetapp.urls")),
    path("notification/", include("notification.urls")),
    path("communication/", include("com_app.communication.urls")),
    path("hr/dashboard/", include("hr_apps.HRapp.urls")),
    path("hr/recruitment/", include("hr_apps.vacancy.urls")),
    path("hr/performance/", include("hr_apps.appraisals.urls")),
    path("procurement/", include("procurement.procureapp.urls")),
    path("finance_app/finance/", include("finance_app.finance.urls")),
    path("procurement/core/", include(("core.urls", "core"), namespace="procurement_core")),
    path("mne/core/", include(("core.urls", "core"), namespace="mne_core")),
    path("mne/monitoring/", include("mne.monitoring.urls")),
    path("garcis/", include(("risk_apps.garcis_urls", "garcis_core"), namespace="garcis")),
    path("garcis/governance/", include("risk_apps.governance.urls")),
    path("garcis/audit/", include("risk_apps.audit.urls")),
    path("garcis/analytics/", include("risk_apps.analytics.urls")),
    path("garcis/compliance/", include("risk_apps.compliance.urls")),
    path("garcis/risk/", include("risk_apps.risk.urls")),
    path("", include("account.urls")),
    path("", lambda request: redirect("system_home") if request.user.is_authenticated else redirect("login")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
