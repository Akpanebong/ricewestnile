from django.db import migrations

# (code, name, is_group, [children...]) — mirrors the standard multi-level
# Assets breakdown the user referenced (Current Assets split into Cash,
# Bank, Receivables, Stock, Tax, and Loans & Advances, plus Fixed Assets /
# Investments / Temporary Accounts as siblings), built under the existing
# "1000 Assets" root rather than replacing it.
ASSET_TREE = (
    "1100-1600", "Current Assets", True, [
        ("1100", "Cash In Hand", True, [
            ("1110", "Cash", False, []),
        ]),
        ("1200", "Bank Accounts", True, []),
        ("1300", "Accounts Receivable", True, [
            ("1310", "Debtors", False, []),
        ]),
        ("1400", "Stock Assets", True, [
            ("1410", "Stock In Hand", False, []),
        ]),
        ("1500", "Tax Assets", True, []),
        ("1600", "Loans and Advances (Assets)", True, [
            ("1610", "Employee Advances", False, []),
            ("1650", "Securities and Deposits", True, [
                ("1651", "Earnest Money", False, []),
            ]),
            ("1660", "Prepaid Expenses", False, []),
            ("1670", "Short-term Investments", False, []),
        ]),
    ],
)

TOP_LEVEL_SIBLINGS = (
    ("1700", "Fixed Assets", True, []),
    ("1800", "Investments", True, []),
    ("1900", "Temporary Accounts", True, []),
)

# Existing accounts (created before this hierarchy existed) that fit
# clearly under one of the new groups — re-parented, not recreated, so
# their linked transactions and history are untouched.
REPARENT_BY_CODE = {
    "1010": "1700",  # Capital Expenditure / Asset Purchase -> Fixed Assets
    "1020": "1600",  # Fund Advance / Transfer -> Loans and Advances (Assets)
    "1030": "1600",  # Inter-Fund Transfer -> Loans and Advances (Assets)
}


def create_tree(FinancialCategory, base_currency, parent, code, name, is_group, children, category_type):
    node = FinancialCategory.objects.create(
        code=code, name=name, category_type=category_type, parent=parent,
        is_group=is_group, currency=base_currency,
    )
    for child_code, child_name, child_is_group, grandchildren in children:
        create_tree(FinancialCategory, base_currency, node, child_code, child_name, child_is_group, grandchildren, category_type)
    return node


def expand_assets(apps, schema_editor):
    FinancialCategory = apps.get_model("finance", "FinancialCategory")
    from core.services import get_base_currency
    base_currency = get_base_currency()

    assets_root = FinancialCategory.objects.get(code="1000")
    category_type = assets_root.category_type

    # The old empty "Receivables" placeholder (code 1100) is superseded by
    # the new "1300 Accounts Receivable" group below and would otherwise
    # collide with the new "1100 Cash In Hand" group's code. Safe to
    # remove outright: it has no children and no transactions (verified
    # before writing this migration).
    FinancialCategory.objects.filter(code="1100", parent=assets_root, is_group=True, name="Receivables").delete()

    code, name, is_group, children = ASSET_TREE
    create_tree(FinancialCategory, base_currency, assets_root, code, name, is_group, children, category_type)

    for code, name, is_group, children in TOP_LEVEL_SIBLINGS:
        create_tree(FinancialCategory, base_currency, assets_root, code, name, is_group, children, category_type)

    # Re-parent targets (1600, 1700) sit nested inside the new tree, not as
    # direct children of the root, so look them up by code directly.
    targets = {c.code: c for c in FinancialCategory.objects.filter(code__in=set(REPARENT_BY_CODE.values()))}
    for old_code, new_parent_code in REPARENT_BY_CODE.items():
        account = FinancialCategory.objects.filter(code=old_code).first()
        new_parent = targets.get(new_parent_code)
        if account and new_parent:
            account.parent = new_parent
            account.save(update_fields=["parent"])


def noop_reverse(apps, schema_editor):
    # Not safely reversible — re-parented accounts and the deleted
    # placeholder can't be restored to their exact prior state.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0009_renumber_leaf_accounts_to_numeric_codes"),
    ]

    operations = [
        migrations.RunPython(expand_assets, noop_reverse),
    ]
