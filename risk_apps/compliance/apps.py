from django.apps import AppConfig


class ComplianceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'risk_apps.compliance'

    def ready(self):
        from . import signals  # 👈 This line loads your signals

