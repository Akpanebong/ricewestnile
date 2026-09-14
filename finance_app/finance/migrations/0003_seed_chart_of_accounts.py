from django.db import migrations


DEFAULT_CHART_OF_ACCOUNTS = [
    # Income
    ("DONOR-INC", "Donor Income", "income"),
    ("GRANT-INC", "Grant Income", "income"),
    ("OTHER-INC", "Other Income", "income"),

    # Expense
    ("PROG-EXP", "Program Expenditure", "expense"),
    ("ADMIN-EXP", "Administrative Expense", "expense"),
    ("PAYROLL-EXP", "Payroll & Personnel Costs", "expense"),
    ("MAINT-EXP", "Asset Maintenance & Repairs", "expense"),
    ("PROC-EXP", "Procurement & Supplies", "expense"),
    ("BANK-CHG", "Bank Charges & Fees", "expense"),

    # Transfer (folded into Assets — a fund advance/transfer is a movement
    # of a fund balance, not an income/expense/equity event of its own)
    ("FUND-ADV", "Fund Advance / Transfer", "asset"),
    ("INTERFUND", "Inter-Fund Transfer", "asset"),

    # Capital (folded into Assets)
    ("CAPEX", "Capital Expenditure / Asset Purchase", "asset"),
]


def seed_chart_of_accounts(apps, schema_editor):
    FinancialCategory = apps.get_model("finance", "FinancialCategory")
    for code, name, category_type in DEFAULT_CHART_OF_ACCOUNTS:
        FinancialCategory.objects.get_or_create(
            code=code,
            defaults={"name": name, "category_type": category_type},
        )


def noop_reverse(apps, schema_editor):
    # Deliberately not deleting categories on reverse — by the time anyone
    # would roll this back, real FinancialTransaction rows may reference
    # them (on_delete=PROTECT), and removing reference data isn't safe to
    # automate blindly.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0002_financialcategory_financialtransaction"),
    ]

    operations = [
        migrations.RunPython(seed_chart_of_accounts, noop_reverse),
    ]
