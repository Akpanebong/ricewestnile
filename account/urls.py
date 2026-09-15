from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views


urlpatterns = [

    # Authentication
    path("", auth_views.LoginView.as_view(template_name="account/login.html"), name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Password management
    path("password_change/", auth_views.PasswordChangeView.as_view(
        template_name="account/password_change.html"), name="password_change"),
    path("password_change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="account/password_change_done.html"), name="password_change_done"),

    # forgotten password
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', views.reset_password, name='reset_password'),


    # Department URLs
    path('departments/', views.department_list, name='department_list'),
    path('departments/create/', views.department_create, name='department_create'),
    path('departments/<int:pk>/edit/', views.department_update, name='department_update'),
    path('departments/<int:pk>/delete/', views.department_delete, name='department_delete'),

    path('departments/units/', views.units_for_department, name='units_for_department'),
    path('units/projects/', views.projects_for_unit, name='projects_for_unit'),

    # Unit URLs
    path('units/', views.unit_list, name='unit_list'),
    path('units/create/', views.unit_create, name='unit_create'),
    path('units/<int:pk>/edit/', views.unit_update, name='unit_update'),
    path('units/<int:pk>/delete/', views.unit_delete, name='unit_delete'),

    # Program Area URLs
    path('program-areas/', views.program_area_list, name='program_area_list'),
    path('program-areas/create/', views.program_area_create, name='program_area_create'),
    path('program-areas/<int:pk>/edit/', views.program_area_update, name='program_area_update'),
    path('program-areas/<int:pk>/delete/', views.program_area_delete, name='program_area_delete'),

    # Search
    path('search/', views.global_search, name='global_search'),

    # Profile URLs
    path('update_profile/<slug:slug>/', views.update_profile, name='update_employee'),
    path('profiles/', views.profile_list, name='profile_list'),
    path('profiles/create/', views.profile_create, name='profile_create'),
    path('profiles/import/', views.import_employees, name='import_employees'),
    path('profiles/import/template/', views.download_employee_import_template, name='download_employee_import_template'),
    path('profiles/<int:pk>/update/<slug:slug>/', views.employee_profile_update, name='profile_update'),
    path('profiles/<int:pk>/delete/', views.profile_delete, name='profile_delete'),
    path('profiles/<int:pk>/reset-password/', views.admin_reset_password, name='admin_reset_password'),

    # Exit flow (HR updates, CMT views)
    path("exit-flow/hr/", views.exit_process_hr_list, name="account_exit_process_hr_list"),
    path(
        "exit-flow/hr/<slug:staff_slug>/",
        views.exit_process_hr_update,
        name="account_exit_process_update",
    ),
    path("exit-flow/cmt/", views.exit_process_cmt_list, name="account_exit_process_cmt_list"),
    path(
        "exit-flow/cmt/<slug:staff_slug>/",
        views.exit_process_cmt_detail,
        name="account_exit_process_cmt_detail",
    ),
]
