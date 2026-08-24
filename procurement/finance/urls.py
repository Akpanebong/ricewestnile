from django.urls import path
from . import views

app_name = "finance"

urlpatterns = [

    # DASHBOARD
    path("", views.dashboard, name="dashboard"),

    # =========================
    # CASH REQUISITION
    # =========================
    path("fund/requisition/", views.create_cash_requisition, name="create_cash_req"),
    path("fund/requisition/procurement/<int:req_pk>/", views.create_cash_requisition_from_procurement, name="create_cash_req_from_procurement"),
    path("fund/requisitions/", views.requisition_list, name="list_cash_req"),
    path("requisition/<int:pk>/<slug:slug>/", views.requisition_detail, name="requisition_detail"),

    path("requisition/<int:pk>/submit/<slug:slug>/", views.submit_requisition, name="submit_cash_req"),
    path("requisition/<int:pk>/approve/<slug:slug>/", views.approve_requisition, name="approve_cash_req"),
    path("requisition/<int:pk>/reject/<slug:slug>/", views.reject_requisition, name="reject_cash_req"),

    path("requisition/<int:pk>/pdf/<slug:slug>/", views.requisition_pdf, name="cash_req_pdf"),

    # ADMIN EXPENSE
    path("admin-expense/<slug:slug>/<int:pk>/create/", views.create_admin_expense, name="create_admin_expense"),
    path("admin-expense/<int:pk>/<slug:slug>/", views.admin_expense_detail, name="admin_expense_detail"),
    path("admin-expense/<int:pk>/submit/<slug:slug>/", views.submit_admin_expense, name="submit_admin_expense"),
    path("admin-expense/<int:pk>/approve/<slug:slug>/", views.approve_admin_expense, name="approve_admin_expense"),
    path("admin-expense/<int:pk>/pdf/<slug:slug>/", views.admin_expense_pdf, name="admin_expense_pdf"),

    # =========================
    # ACCOUNTING (RETIREMENT)
    # =========================
    # path("accounting/<slug:slug>/<int:pk>/create/", views.create_accounting, name=
    path("accounting/<slug:slug>/<int:pk>/", views.save_accounting, name="save_accounting"),
    path("accounting/create/<slug:req_slug>/<int:req_pk>/", views.save_accounting, name="create_accounting"),
    path("accounting/<int:pk>/<slug:slug>/", views.accounting_detail, name="accounting_detail"),
    path("accounting/<int:pk>/pdf/<slug:slug>/", views.accounting_pdf, name="accounting_pdf"),
    path("accounting/<int:pk>/approval/<slug:slug>/", views.approve_account_form, name="approve_account_form"),
]
