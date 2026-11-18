from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring", "0002_indicator_target"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dataentry",
            name="value",
            field=models.FloatField(
                blank=True,
                help_text="Captured value",
                null=True,
            ),
        ),
    ]
