from decimal import Decimal

from django.db import migrations
from django.db.models import F


def backfill(apps, schema_editor):
    FinancialTransaction = apps.get_model("finance", "FinancialTransaction")
    # Every transaction created before this migration was recorded natively
    # in UGX (see the model docstring / classmethod comments), so
    # original_amount == amount and the rate used was 1-for-1.
    FinancialTransaction.objects.filter(original_amount__isnull=True).update(
        original_amount=F("amount"),
        exchange_rate_used=Decimal("1"),
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0004_financialtransaction_currency_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, noop_reverse),
    ]
