from django.urls import path
from . import project_views as pro
from . import views


app_name = "core"

urlpatterns = [
    # Currency settings lives at the single canonical route registered in
    # enterprise/urls.py (name="currency_settings") — not duplicated here
    # under this urls.py's two namespace mounts (procurement_core/mne_core).

    path("location/", views.LocationListView.as_view(), name="location_list"),
    path("trash/<int:pk>/<str:sub_county>/location/", views.trash_location, name="trash_location"),
    path("update/<str:sub_county>/<int:pk>/location/", views.location_update, name="location_update"),
    path("create/location/", views.create_location, name="location_create"),
    path("project/", pro.project_list, name="project_list"),
    path("trash/<int:pk>/<str:name>/project/", pro.project_delete, name="trash_project"),
    path("update/<int:pk>/project/<slug:slug>/", pro.project_update, name="project_update"),
    path("create/project/", pro.project_create, name="project_create"),
    path("project/<int:pk>/<slug:slug>/documents/", pro.project_documents, name="project_documents"),
    path("project/<int:pk>/<slug:slug>/documents/<str:document_type>/upload/", pro.project_document_upload, name="project_document_upload"),
    path("project/<int:pk>/<slug:slug>/documents/<int:document_id>/confirm/", pro.project_activity_confirm, name="project_activity_confirm"),
    path("project/<int:pk>/<slug:slug>/activity/<int:activity_id>/concept-note/", pro.activity_concept_note_detail, name="activity_concept_note_detail"),
    path("project/<int:pk>/<slug:slug>/activity/<int:activity_id>/concept-note/online/", pro.activity_concept_note_entry, name="activity_concept_note_entry"),
    path("project/<int:pk>/<slug:slug>/activity/<int:activity_id>/concept-note/upload/", pro.activity_concept_note_upload, name="activity_concept_note_upload"),
    path("project/<int:pk>/<slug:slug>/activity/<int:activity_id>/concept-note/submit/", pro.activity_concept_note_submit, name="activity_concept_note_submit"),
    path("project/<int:pk>/<slug:slug>/activity/<int:activity_id>/concept-note/review/", pro.activity_concept_note_review, name="activity_concept_note_review"),
    path("project/<int:pk>/<slug:slug>/activity/<int:activity_id>/concept-note/approve/", pro.activity_concept_note_approve, name="activity_concept_note_approve"),
    path("project/<int:pk>/<slug:slug>/reporting/", pro.project_reporting_input, name="project_reporting_input"),
    path("project/cmt-reporting/all/", pro.cmt_reporting_all, name="cmt_reporting_all"),
    path("project/cmt-reporting/all/stakeholder/download/", pro.cmt_all_stakeholder_export, name="cmt_all_stakeholder_export"),
    path("project/cmt-reporting/all/meetings/download/", pro.cmt_all_team_meetings_export, name="cmt_all_team_meetings_export"),
    path("project/<int:pk>/<slug:slug>/cmt-reporting/", pro.cmt_project_reporting, name="cmt_project_reporting"),
    path("project/<int:pk>/<slug:slug>/cmt-reporting/submission/<int:submission_id>/download/", pro.cmt_project_submission_download, name="cmt_project_submission_download"),
    path("project/<int:pk>/<slug:slug>/cmt-reporting/stakeholder/download/", pro.cmt_stakeholder_updates_download, name="cmt_stakeholder_export"),
    path("project/<int:pk>/<slug:slug>/cmt-reporting/meetings/download/", pro.cmt_team_meetings_download, name="cmt_team_meetings_export"),
    path("resources/", views.resource_list, name="resource_list"),
    path("resources/download/<int:pk>/", views.download_resource, name="download_resource"),
    path("resources/delete/<int:pk>/", views.resource_delete, name="resource_delete"),
    path("resources/upload/", views.resource_upload, name="resource_upload"),
]
