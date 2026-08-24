from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import JobOpening


@receiver(post_save, sender=JobOpening)
def auto_close_job(sender, instance, **kwargs):
    instance.auto_close_if_expired()