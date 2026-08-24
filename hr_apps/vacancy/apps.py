from django.apps import AppConfig


class VacancyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hr_apps.vacancy'

    def ready(self):
        from . import signals
