from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0026_expand_bank_reconciliation_item_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashbook",
            name="cashbook_type",
            field=models.CharField(
                choices=[
                    ("mobile_money", "Mobile money"),
                    ("bank", "Bank"),
                    ("petty", "Petty cash"),
                ],
                default="bank",
                max_length=20,
            ),
        ),
    ]
