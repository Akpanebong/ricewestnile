from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from monitoring.models import DataEntry

class Command(BaseCommand):
    help = 'Create default M&E roles'

    def handle(self, *args, **options):
        roles = ['ME_Admin','ME_Officer','Data_Collector']
        for r in roles:
            g, created = Group.objects.get_or_create(name=r)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group {r}'))
            else:
                self.stdout.write(f'Group {r} exists')
        # Add sample permission: Data_Collector can add DataEntry
        try:
            ct = ContentType.objects.get_for_model(DataEntry)
            perm = Permission.objects.get(content_type=ct, codename='add_dataentry')
            collector = Group.objects.get(name='Data_Collector')
            collector.permissions.add(perm)
            self.stdout.write(self.style.SUCCESS('Assigned add_dataentry to Data_Collector'))
        except Exception as e:
            self.stdout.write(str(e))