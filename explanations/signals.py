from django.db.models.signals import post_save
from django.dispatch import receiver

from attendance.models import AttendanceRecord


@receiver(post_save, sender=AttendanceRecord)
def late_explanation(sender, instance, **kwargs):
    if instance.late_minutes > 0 and instance.company.auto_explanation:
        from .services import create_for_lateness

        create_for_lateness(instance)
