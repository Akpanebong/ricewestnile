from django.db import migrations

# Old short-form code -> new numeric code, banded under each root group the
# same way the root groups themselves are numbered (1000s Assets, 2000s
# Liabilities, 3000s Equity, 4000s Income, 5000s Expenses). Sub-group bands
# (1100 Receivables, 2100 Payables) are left room by starting leaf accounts
# at <root>+10 and stepping by 10, not <root>+100.
RENUMBER = {
    "CAPEX": "1010",
    "FUND-ADV": "1020",
    "INTERFUND": "1030",
    "DONOR-INC": "4010",
    "GRANT-INC": "4020",
    "OTHER-INC": "4030",
    "ADMIN-EXP": "5010",
    "BANK-CHG": "5020",
    "MAINT-EXP": "5030",
    "PAYROLL-EXP": "5040",
    "PROC-EXP": "5050",
    "PROG-EXP": "5060",
}


def renumber_forward(apps, schema_editor):
    FinancialCategory = apps.get_model("finance", "FinancialCategory")
    for old_code, new_code in RENUMBER.items():
        category = FinancialCategory.objects.filter(code=old_code).first()
        if not category:
            continue
        # The old mnemonic code is still worth keeping around as a secondary
        # reference (what alt_code is for) — but don't clobber one someone
        # already set.
        if not category.alt_code:
            category.alt_code = old_code
        category.code = new_code
        category.save(update_fields=["code", "alt_code"])


def renumber_reverse(apps, schema_editor):
    FinancialCategory = apps.get_model("finance", "FinancialCategory")
    for old_code, new_code in RENUMBER.items():
        category = FinancialCategory.objects.filter(code=new_code).first()
        if not category:
            continue
        category.code = old_code
        if category.alt_code == old_code:
            category.alt_code = ""
        category.save(update_fields=["code", "alt_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0008_add_account_hierarchy_and_currency"),
    ]

    operations = [
        migrations.RunPython(renumber_forward, renumber_reverse),
    ]
