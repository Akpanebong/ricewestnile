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

    # =========================
    # FINANCIAL LEDGER & REPORTING
    # =========================
    path("ledger/", views.financial_ledger, name="ledger"),
    path("ledger/export/", views.financial_ledger_export, name="ledger_export"),
    path("chart-of-accounts/", views.chart_of_accounts, name="chart_of_accounts"),
    path("chart-of-accounts/add/", views.add_account, name="add_account"),
    path("chart-of-accounts/<int:pk>/delete/", views.delete_account, name="delete_account"),
    path("reports/", views.reports_home, name="reports_home"),
    path("reports/general-ledger/", views.general_ledger_report, name="general_ledger_report"),
    path("reports/general-ledger/view/", views.general_ledger_report_view, name="general_ledger_report_view"),
    path("reports/income-statement/", views.income_statement_report, name="income_statement_report"),
    path("reports/income-statement/view/", views.income_statement_report_view, name="income_statement_report_view"),
    path("reports/budget-vs-actual/", views.budget_vs_actual_report, name="budget_vs_actual_report"),
    path("reports/budget-vs-actual/view/", views.budget_vs_actual_report_view, name="budget_vs_actual_report_view"),
    path("reports/balance-sheet/", views.balance_sheet_report, name="balance_sheet_report"),
    path("reports/balance-sheet/view/", views.balance_sheet_report_view, name="balance_sheet_report_view"),
    path("journal-entries/", views.journal_entry_list, name="journal_entry_list"),
    path("journal-entries/new/", views.journal_entry_create, name="journal_entry_create"),
    path("journal-entries/<int:pk>/", views.journal_entry_detail, name="journal_entry_detail"),
]
