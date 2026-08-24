from django.urls import path
from . import views

app_name = 'vacancy'

urlpatterns = [
    # Recruitment
    path("request/create/", views.recruitment_request_create, name="recruitment_request_create"),
    path("request/list/", views.recruitment_request_list, name="recruitment_request_list"),
    path("request/<int:pk>/<slug:slug>/", views.trash_recruitment_request, name="trash_recruitment_request"),
    path("request/<int:pk>/hr-review/<slug:slug>/", views.hr_review, name="hr_review"),
    path("request/<int:pk>/ed-approve/<slug:slug>/", views.ed_approve, name="ed_approve"),
    path("request/ed-approve-confirm/<slug:slug>/", views.ed_approve_confirm, name="ed_approve_confirm"),
    path("request/<int:pk>/publish/<slug:slug>/", views.publish_job, name="publish_job"),

    path("jobs/", views.job_list, name="job_list"),
    path("jobs/<int:pk>/modal/", views.job_detail_modal, name="job_detail_modal"),
    path("jobs/<int:pk>/edit/<slug:slug>/", views.edit_job_opening, name="edit_job_opening"),
    path("request/<slug:slug>/<int:pk>/", views.trash_job_opening, name="trash_job"),
    path("jobs/<int:pk>/apply/", views.apply_job, name="apply_job"),

    # Applicants (HR)
    path("applicants/", views.applicants_list, name="applicants_list"),
    path("applicants/<int:pk>/review/", views.applicant_review, name="applicant_review"),
    path("applicants/<int:pk>/send-result/", views.send_applicant_result, name="send_applicant_result"),
]


