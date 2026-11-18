from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="indicator",
            name="target",
            field=models.FloatField(blank=True, help_text="Target value", null=True),
        ),
    ]
