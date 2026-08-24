from django.contrib import admin


from .models import JobOpening, Applicant, RecruitmentRequest


# ---------------------------
# Job Opening Admin
# ---------------------------
@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    list_display = ['is_active', 'posted_at']
    list_filter = ['is_active']
    # search_fields = ('department')
    date_hierarchy = 'posted_at'


# ---------------------------
# Applicant Admin
# ---------------------------
@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'job', 'status', 'applied_at')
    list_filter = ('status', 'job')
    search_fields = ('full_name', 'email')
    date_hierarchy = 'applied_at'


admin.site.register(RecruitmentRequest)
