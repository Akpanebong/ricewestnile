from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notification", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="source_app",
            field=models.CharField(
                choices=[
                    ("core", "Core"),
                    ("hr", "Human Resource"),
                    ("procurement", "Procurement"),
                    ("communication", "Communication"),
                    ("mne", "Monitoring & Evaluation"),
                    ("governance", "Governance"),
                ],
                db_index=True,
                default="core",
                max_length=30,
            ),
        ),
    ]
