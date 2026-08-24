from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from procurement.procureapp.models import (Supplier, Requisition, RequisitionItem, PurchaseOrder)
import datetime

User = get_user_model()


class Command(BaseCommand):
    help = "Create demo groups, users and sample procurement data"

    def handle(self, *args, **options):
        groups = ['Procurement Officer','Project/Department Head','Finance Officer','Supplier','Admin']
        for name in groups:
            Group.objects.get_or_create(name=name)
        # create users
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin','admin@example.com','admin123')
            self.stdout.write("Created admin/admin123")
        if not User.objects.filter(username='proc_officer').exists():
            u = User.objects.create_user('proc_officer','po@example.com','proc123')
            g = Group.objects.get(name='Procurement Officer'); u.groups.add(g)
        if not User.objects.filter(username='head').exists():
            u = User.objects.create_user('head','head@example.com','head123')
            g = Group.objects.get(name='Project/Department Head'); u.groups.add(g)
        if not User.objects.filter(username='finance').exists():
            u = User.objects.create_user('finance','fin@example.com','fin123')
            g = Group.objects.get(name='Finance Officer'); u.groups.add(g)
        if not User.objects.filter(username='supplier1').exists():
            u = User.objects.create_user('supplier1','supp@example.com','supp123')
            g = Group.objects.get(name='Supplier'); u.groups.add(g)

        s1, _ = Supplier.objects.get_or_create(title='Mr.', defaults={'active': True})
        s2, _ = Supplier.objects.get_or_create(title='Dr.', defaults={'active': True})

        if not Requisition.objects.filter(number='DEMO-PR-001').exists():
            req = Requisition.objects.create(number='DEMO-PR-001', created_by=User.objects.get(username='proc_officer'), status='Approved')
            RequisitionItem.objects.create(po=req, description='A4 Paper', qty=10, unit_price=5)
            RequisitionItem.objects.create(po=req, description='Pens (box)', qty=5, unit_price=10)
            self.stdout.write("Created demo requisition")

        req = Requisition.objects.get(number='DEMO-PR-001')
        if not PurchaseOrder.objects.filter(number='DEMO-PO-001').exists():
            po = PurchaseOrder.objects.create(number='DEMO-PO-001', requisition=req, supplier=s1, issued_by=User.objects.get(username='proc_officer'), total=100)
            self.stdout.write("Created demo PO")

        self.stdout.write(self.style.SUCCESS("Demo data created"))
