import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from django.db import models
from account.models import Profile

ASSET_CATEGORIES = (
    ('VEHICLE', 'Vehicle'),
    ('MOTORCYCLE', 'Motorcycle'),
    ('ICT', 'ICT Equipment'),
    ('FURNITURE', 'Furniture'),
    ('OFFICE', 'Office Equipment'),
    ('LAND', 'Land'),
    ('BUILDING', 'Building'),
    ('PLANT', 'Plant & Machinery'),
)

MODE_OF_ACQUISITION = (
    ('PROJECT FUNDED', 'Project Funded'),
    ('LOAN', 'Loan'),
    ('CAPITAL', 'Capital'),
)


class Asset(models.Model):
    asset_no = models.CharField(max_length=100, unique=True)
    date_of_entry = models.DateField()
    category = models.CharField(max_length=50, choices=ASSET_CATEGORIES)

    description = models.TextField()
    purchase_value = models.DecimalField(max_digits=15, decimal_places=2)
    allocation = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True,)
    serial_no = models.CharField(max_length=100, blank=True, null=True)
    chasis_no = models.CharField(max_length=100, blank=True, null=True)
    engine_no = models.CharField(max_length=100, blank=True, null=True)

    place = models.CharField(max_length=100)
    mode_of_acquisition = models.CharField(max_length=100, choices=MODE_OF_ACQUISITION, default='PROJECT FUNDED')

    additions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    usage_years = models.PositiveIntegerField()

    depreciation_rate = models.DecimalField(max_digits=10, decimal_places=2)
    depreciation_accumulated = models.DecimalField(max_digits=15, decimal_places=2, default=0, editable=False)

    write_offs = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    comments = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def __str__(self):
        return self.asset_no

    class Meta:
        ordering = ['asset_no']

    # def calculate_depreciation(self):
    #     years_used = (date.today() - self.date_of_entry).days / 365
    #     annual = self.purchase_value * (self.depreciation_rate / 100)
    #     return min(round(annual * years_used, 2), self.purchase_value)

    def calculate_depreciation(self):
        """
        Straight-line depreciation using Decimal only.
        """

        if not self.date_of_entry or not self.purchase_value or not self.depreciation_rate:
            return Decimal("0.00")

        days_used = (date.today() - self.date_of_entry).days

        # Convert days to years using Decimal
        years_used = Decimal(days_used) / Decimal("365")

        annual_depreciation = (
                self.purchase_value * (self.depreciation_rate / Decimal("100"))
        )

        accumulated = annual_depreciation * years_used

        # Do not depreciate beyond purchase value
        if accumulated > self.purchase_value:
            accumulated = self.purchase_value

        return accumulated.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def save(self, *args, **kwargs):
        self.depreciation_accumulated = self.calculate_depreciation()
        if not self.slug:
            self.slug = uuid.uuid4().hex[:10]
        super().save(*args, **kwargs)

    @property
    def net_book_value(self):
        return max(
            self.purchase_value + self.additions -
            self.depreciation_accumulated - self.write_offs,
            0
        )


class AssetMaintenance(models.Model):
    asset = models.ForeignKey(
        Asset, related_name='maintenances', on_delete=models.CASCADE
    )
    maintenance_type = models.CharField(max_length=20)
    description = models.TextField()
    cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    maintenance_date = models.DateField()
    next_due_date = models.DateField(blank=True, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-maintenance_date']


class AuditLog(models.Model):
    ACTIONS = (
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('EXPORT', 'Export'),
        ('MAINTENANCE', 'Maintenance'),
    )

    user = models.ForeignKey(Profile, null=True, on_delete=models.SET_NULL, related_name='asset_audit_logs')
    action = models.CharField(max_length=20, choices=ACTIONS)
    model_name = models.CharField(max_length=100)
    object_id = models.PositiveIntegerField()
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
