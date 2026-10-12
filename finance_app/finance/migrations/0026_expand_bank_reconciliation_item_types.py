from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0025_alter_financebudgetline_outcome"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bankreconciliationitem",
            name="item_type",
            field=models.CharField(
                choices=[
                    ("payment", "Payment in cash book, not on statement"),
                    ("receipt", "Receipt on statement, not in cash book"),
                    ("payment_statement", "Payment on statement, not in cash book"),
                    ("receipt_cashbook", "Receipt on cash book, not on statement"),
                ],
                max_length=20,
            ),
        ),
    ]
