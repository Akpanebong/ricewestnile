from django.apps import AppConfig

class CommunicationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'com_app.communication'


    def ready(self):
        # import signals
        try:
            from . import signals
        except Exception:
            pass
