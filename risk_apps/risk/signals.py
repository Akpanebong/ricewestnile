from django.db.models.signals import post_save
from django.dispatch import receiver
from notification.models import Notification
from notification.utils import notify
from risk_apps.risk.models import Risk


@receiver(post_save, sender=Risk)
def risk_alert(sender, instance, created, **kwargs):
    if instance.risk_level in ["HIGH", "VERY HIGH"]:
        if instance.created_by:
            notify(
                title="⚠ High Risk Alert",
                message=f"⚠ High Risk: {instance.event[:50]}",
                users=instance.created_by,
                category=Notification.Category.ERROR,
                source_app=Notification.Source.CORE
            )
