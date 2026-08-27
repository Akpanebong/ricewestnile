import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F

from account.models import Profile


class Employee(models.Model):
    user = models.OneToOneField(Profile, on_delete=models.SET_NULL, null=True)
    staff_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    job_title = models.CharField(max_length=100, null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    department = models.ForeignKey("account.Department", on_delete=models.SET_NULL, null=True, blank=True)
    supervised_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)

    date_joined = models.DateTimeField(null=True, blank=True)
    # employment_status = models.CharField(max_length=50, default="ACTIVE")

    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def __str__(self):
        if self.user:
            return f'{self.user.get_full_name() or self.user.username}'
        return self.staff_id

    # 🔒 MODEL VALIDATION
    def clean(self):
        if self.supervised_by and self.supervised_by == self:
            raise ValidationError("An employee cannot supervise themselves.")

    def save(self, *args, **kwargs):
        # Enforce validation even when using shell/admin
        self.full_clean()

        if not self.slug:
            self.slug = uuid.uuid4().hex[:10]

        if not self.staff_id and self.user_id:
            self.staff_id = f"R-{self.user_id}"

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-date_joined']
        verbose_name = "Employee Detail"

        # 🛡️ DB-LEVEL PROTECTION
        constraints = [
            models.CheckConstraint(
                check=~Q(id=F('supervised_by')),
                name="employee_prevent_self_supervision",
            )
        ]



class EmployeePersonalInfo(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE)

    marital_status = models.CharField(max_length=80, blank=True)
    sex = models.CharField(max_length=40, blank=True)
    ethnicity = models.CharField(max_length=100, blank=True)
    blood_group = models.CharField(max_length=20, blank=True)

    date_of_birth = models.DateField(null=True)
    age = models.PositiveSmallIntegerField(null=True)

    national_id_no = models.CharField(max_length=100, blank=True)
    passport_no = models.CharField(max_length=100, blank=True)
    work_permit_no = models.CharField(max_length=100, blank=True)


class EmployeeAddress(models.Model):
    ADDRESS_TYPES = (
        ("PERMANENT", "Permanent"),
        ("PRESENT", "Present"),
        ("OFFICE", "Office"),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=ADDRESS_TYPES)

    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    address = models.TextField()
    postal_code = models.CharField(max_length=20, blank=True)


class EmployeeContact(models.Model):
    CONTACT_TYPES = (
        ("PERSONAL", "Personal"),
        ("OFFICIAL", "Official"),
        ("HOME", "Home"),
    )

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=CONTACT_TYPES)

    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)


class EmergencyContact(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)

    name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)
    address = models.TextField(blank=True)


class Dependant(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)

    name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True)


class EducationHistory(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)

    institution = models.CharField(max_length=255)
    qualification = models.CharField(max_length=255)
    year_graduated = models.IntegerField(null=True)
    certifications = models.TextField(blank=True)


class WorkExperience(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)

    company = models.CharField(max_length=255)
    position = models.CharField(max_length=255)
    years = models.IntegerField(default=2020)
    skills = models.TextField(blank=True)


class BankDetail(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE)

    bank_name = models.CharField(max_length=150)
    branch = models.CharField(max_length=150)
    account_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=100)
    swift_code = models.CharField(max_length=80)


