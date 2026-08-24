def currency_context(request):
    try:
        from .models import CurrencyRate
        from .services import CURRENCY_LABELS, SUPPORTED_CURRENCIES, get_latest_usd_rates, get_user_currency

        rates = get_latest_usd_rates()
        ugx_rate = rates[CurrencyRate.UGX]
        display_currency = get_user_currency(request)
        display_rate = rates[display_currency]
        manual_rates = [rate for rate in rates.values() if rate.is_manual]
        active_rate = display_rate or ugx_rate
        return {
            "display_currency": display_currency,
            "display_currency_rate": display_rate.rate,
            "display_currency_from_ugx_rate": display_rate.rate / ugx_rate.rate,
            "usd_ugx_rate": ugx_rate.rate,
            "currency_rate_source": active_rate.source,
            "currency_rate_date": active_rate.rate_date,
            "currency_rate_input_by": active_rate.input_by,
            "currency_rate_is_manual": bool(manual_rates),
            "currency_rate_is_fallback": any(rate.is_fallback for rate in rates.values()),
            "currency_choices": SUPPORTED_CURRENCIES,
            "currency_labels": CURRENCY_LABELS,
        }
    except Exception:
        return {}


def global_dashboard(request):
    if not request.user.is_authenticated:
        return {}
    try:
        from audit.models import AuditFinding
        from compliance.models import ComplianceTask
        from risk.models import Risk

        return {
            "total_risks": Risk.objects.count(),
            "high_risks": Risk.objects.filter(risk_level__in=["HIGH", "VERY HIGH"]).count(),
            "open_findings": AuditFinding.objects.exclude(status="closed").count(),
            "overdue_compliance_tasks": ComplianceTask.objects.filter(status="overdue").count(),
        }
    except Exception:
        return {}


def site_settings(request):
    return {
        "SITE_NAME": "RICE West Nile - Enterprise",
        "SITE_SHORT": "RICE Enterprise",
        "STATIC_CSS_FILES": [
            "assets/css/assets.css",
            "assets/css/style.css",
            "assets/css/typography.css",
        ],
    }

