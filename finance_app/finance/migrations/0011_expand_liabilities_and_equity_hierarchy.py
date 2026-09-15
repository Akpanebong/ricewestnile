from django.db import migrations

# Lighter than the Assets breakdown (no confirmed reference screenshot for
# these two branches) but enough real structure for the Balance Sheet to
# show something other than "no accounts yet" — standard, uncontroversial
# groupings, following the same numbering convention already established
# (root -> hundreds -> tens -> ones per level of nesting).
LIABILITY_TREE = (
    "2100-2600", "Current Liabilities", True, [
        # "2100 Accounts Payable" reuses the existing empty "Payables"
        # group (created earlier this session) rather than duplicating it
        # — handled in code below, not created here.
        ("2200", "Duties and Taxes", True, [
            ("2210", "Tax Payable", False, []),
        ]),
        ("2300", "Provisions", True, [
            ("2310", "Provision for Expenses", False, []),
        ]),
    ],
)

LIABILITY_TOP_LEVEL_SIBLINGS = (
    ("2700", "Long-term Liabilities", True, []),
    ("2800", "Temporary Liabilities", True, []),
)

EQUITY_TREE = (
    ("3100", "Capital Account", True, [
        ("3110", "Opening Balance Equity", False, []),
    ]),
    ("3200", "Reserves and Surplus", True, []),
)


def create_tree(FinancialCategory, base_currency, parent, code, name, is_group, children, category_type):
    node = FinancialCategory.objects.create(
        code=code, name=name, category_type=category_type, parent=parent,
        is_group=is_group, currency=base_currency,
    )
    for child_code, child_name, child_is_group, grandchildren in children:
        create_tree(FinancialCategory, base_currency, node, child_code, child_name, child_is_group, grandchildren, category_type)
    return node


def expand(apps, schema_editor):
    FinancialCategory = apps.get_model("finance", "FinancialCategory")
    from core.services import get_base_currency
    base_currency = get_base_currency()

    liabilities_root = FinancialCategory.objects.get(code="2000")
    liability_type = liabilities_root.category_type

    code, name, is_group, children = LIABILITY_TREE
    current_liabilities = create_tree(
        FinancialCategory, base_currency, liabilities_root, code, name, is_group, children, liability_type
    )

    # Re-parent the existing "Payables" group (code 2100) under the new
    # "Current Liabilities" group and give it the more descriptive name
    # used elsewhere in this structure — same account, same code, no
    # transactions or children lost.
    payables = FinancialCategory.objects.filter(code="2100", is_group=True).first()
    if payables:
        payables.parent = current_liabilities
        payables.name = "Accounts Payable"
        payables.save(update_fields=["parent", "name"])
        FinancialCategory.objects.create(
            code="2110", name="Creditors", category_type=liability_type,
            parent=payables, is_group=False, currency=base_currency,
        )

    for code, name, is_group, children in LIABILITY_TOP_LEVEL_SIBLINGS:
        create_tree(FinancialCategory, base_currency, liabilities_root, code, name, is_group, children, liability_type)

    equity_root = FinancialCategory.objects.get(code="3000")
    equity_type = equity_root.category_type
    for code, name, is_group, children in EQUITY_TREE:
        create_tree(FinancialCategory, base_currency, equity_root, code, name, is_group, children, equity_type)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0010_expand_assets_hierarchy"),
    ]

    operations = [
        migrations.RunPython(expand, noop_reverse),
    ]
