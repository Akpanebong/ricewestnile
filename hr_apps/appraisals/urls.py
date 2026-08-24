from django.urls import path
from . import views

urlpatterns = [
    path('appraisals/', views.appraisal_list, name='appraisal_list'),
    path('appraisals/dashboard/', views.appraisal_dashboard, name='appraisal_dashboard'),
    path('appraisal/create/<int:employee_id>/', views.create_appraisal, name='create_appraisal'),
    path('appraisal/<int:pk>/', views.appraisal_detail, name='appraisal_detail'),
    path('appraisal/<int:pk>/employee/', views.employee_submit, name='employee_submit'),
    path('appraisal/<int:pk>/supervisor/', views.supervisor_review, name='supervisor_review'),
    path('appraisal/<int:pk>/hr/', views.hr_review, name='hr_review'),
    path('appraisal/<int:pk>/cmt/', views.cmt_approval, name='cmt_approval'),
    path("appraisal/<int:pk>/send-pip/", views.send_pip, name="send_pip",),
    path("pip/<uuid:token>/", views.fill_pip, name="fill_pip",)
]
