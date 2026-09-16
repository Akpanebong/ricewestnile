from django.db import migrations


class Migration(migrations.Migration):
    """Join the cash-book branch pulled from the feature work with the
    collaborator's chart-of-accounts and journal-entry branch.

    Both branches are already represented in the database through their own
    migrations; this migration only makes Django's graph unambiguous.
    """

    dependencies = [
        ("finance", "0002_bankreconciliation_bankreconciliationitem_cashbook_and_more"),
        ("finance", "0012_alter_financialtransaction_transaction_type_and_more"),
    ]

    operations = []
