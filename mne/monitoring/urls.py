from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('data/entry/list/', views.data_entry_list, name='data_entry_list'),
    path('data/entry/<int:pk>/update/', views.update_data_entry, name='update_data_entry'),

    path("indicator/<int:pk>/", views.indicator_detail, name="indicator_detail"),
    path("indicator/", views.IndicatorListView.as_view(), name="indicator_list"),
    path("create/indicator/<int:output_id>/", views.create_indicator, name="create_indicator"),
    path("update/<str:name>/<int:pk>/", views.update_indicator, name="update_indicator"),
    path("trash/<int:pk>/<str:name>/indicator/", views.trash_indicator, name="trash_indicator"),
    path("so/<int:pk>/<str:title>/", views.so_detail, name="so_detail"),
    path("so/", views.SoListView.as_view(), name="so_list"),
    path("create/so/", views.create_so, name="create_so"),
    path("update/<str:title>/<int:pk>/so/", views.update_so, name="update_so"),
    path("trash/<int:pk>/<str:title>/so/", views.trash_so, name="trash_so"),
    path("create/<int:so_id>/output/", views.create_output, name="create_output"),
    path("update/<str:title>/<int:pk>/output/", views.update_output, name="update_output"),
    path("trash/<int:pk>/<str:title>/output/", views.trash_output, name="trash_output"),
    path("detail/<int:pk>/<str:title>/output/", views.output_detail, name="output_detail"),
    path("output/", views.OutputListView.as_view(), name="output_list"),

    path('hierarchy/', views.hierarchy_view, name='hierarchy'),
    path('ajax/so/<int:so_id>/outputs/', views.ajax_outputs_for_so, name='ajax_outputs_for_so'),
    path('ajax/output/<int:output_id>/indicators/', views.ajax_indicators_for_output, name='ajax_indicators_for_output'),
    path('indicator/<int:indicator_id>/entry/', views.entry_form, name='entry_form'),
    path('chart-data/', views.chart_data, name='chart_data'),

    # Export endpoints
    path('export-excel/', views.export_excel, name='export_excel'),
    path('export-pdf/', views.export_pdf, name='export_pdf'),
    path('indicator/<int:pk>/export-excel/', views.export_indicator_excel, name='export_indicator_excel'),
    path('indicator/<int:pk>/export-pdf/', views.export_indicator_pdf, name='export_indicator_pdf'),
    path('csv-import/', views.csv_import, name='csv_import'),
    path('download-csv-template/', views.download_csv_template, name='download_csv_template'),

    path("core-programs/", views.core_program_list, name="core_program_list"),
    path("core-program-chart/<int:pk>/", views.core_program_chart, name="core_program_chart"),

]
