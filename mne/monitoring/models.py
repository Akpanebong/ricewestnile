import uuid

from django.contrib.auth import get_user_model
from django.db import models
from dateutil.relativedelta import relativedelta
from django.utils.text import slugify

from core.project_models import Project, Location, CoreProgram

User = get_user_model()

SEX_CHOICES = [("M","Male"),("F","Female"),("O","Other")]
STATUS_CHOICES = [("Refugee","Refugee"),("National","National")]
ENTERPRISE_TYPES = [
    ("Agriculture","Agriculture"),
    ("Retail","Retail"),
    ("Services","Services"),
    ("Other","Other")
]



class StrategicObjective(models.Model):
    code = models.CharField(max_length=50, help_text='E.g: SO 1', unique=True)   # e.g. 'SO1'
    title = models.CharField(max_length=400)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)[:40]
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.title}"


class Output(models.Model):
    so = models.ForeignKey(StrategicObjective, related_name='outputs', on_delete=models.CASCADE)
    code = models.CharField(max_length=50, help_text='E.g: 1.1', unique=True)   # e.g. '1.1'
    title = models.CharField(max_length=400)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)[:40]
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.so.code} - {self.title}" if not self.code.startswith(f"{self.so.code}.") else f"{self.code} - {self.title}"


class Indicator(models.Model):
    # sub-output / indicator level: e.g. '1.1.1'
    output = models.ForeignKey(Output, related_name='indicators', on_delete=models.CASCADE)
    code = models.CharField(max_length=50, help_text='E.g: 1.1.1', unique=True)  # e.g. '1.1.1'
    name = models.CharField(max_length=400)
    description = models.TextField(blank=True)
    unit_of_measure = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(unique=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)[:40]
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"



class DataEntry(models.Model):
    indicator = models.ForeignKey(Indicator, related_name='entries', on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    donor = models.CharField(max_length=200, blank=True)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=2, choices=SEX_CHOICES, default='M', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='National', null=True, blank=True)
    pwd = models.PositiveIntegerField(null=True, blank=True)
    pwd_nationals = models.PositiveIntegerField(default=0, blank=True)
    pwd_refugees = models.PositiveIntegerField(default=0, blank=True)
    pwd_national_males = models.PositiveIntegerField(default=0, blank=True)
    pwd_refugee_males = models.PositiveIntegerField(default=0, blank=True)
    pwd_national_females = models.PositiveIntegerField(default=0, blank=True)
    pwd_refugee_females = models.PositiveIntegerField(default=0, blank=True)
    enterprise_type = models.CharField(max_length=100, choices=ENTERPRISE_TYPES, null=True, blank=True, default='Other')
    no_of_enterprise = models.PositiveIntegerField(null=True, blank=True)
    no_of_group_reached = models.PositiveIntegerField(null=True, blank=True)
    no_of_group_members = models.PositiveIntegerField(null=True, blank=True)
    no_male = models.PositiveIntegerField(null=True, blank=True)
    no_female = models.PositiveIntegerField(null=True, blank=True)
    value = models.FloatField(null=True, blank=True, help_text='Target')
    program_area = models.ForeignKey(CoreProgram, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(unique=True, blank=True, editable=False)

    class Meta:
        ordering = ['-created_at']

    @property
    def pwd_breakdown_total(self):
        return sum(
            getattr(self, field) or 0
            for field in [
                "pwd_nationals",
                "pwd_refugees",
                "pwd_national_males",
                "pwd_refugee_males",
                "pwd_national_females",
                "pwd_refugee_females",
            ]
        )

    def save(self, *args, **kwargs):
        breakdown_total = self.pwd_breakdown_total
        if breakdown_total:
            self.pwd = breakdown_total
        elif self.pwd is None:
            self.pwd = 0
        if not self.slug:
            self.slug = uuid.uuid4().hex[:40]
            if self.slug:
                self.slug = f"{slugify(self.slug)[:15]}-{uuid.uuid4().hex[:24]}"
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.indicator.code} | {self.year} | {self.location}"
