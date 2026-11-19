import re

from django.db import migrations, models


def populate_indicator_codes(apps, schema_editor):
    Indicator = apps.get_model("monitoring", "StrategicObjectiveIndicator")
    grouped = {}
    for indicator in Indicator.objects.select_related("strategic_objective").order_by("strategic_objective_id", "id"):
        objective_code = indicator.strategic_objective.code or "SO"
        match = re.search(r"(\d+)", objective_code)
        prefix = match.group(1) if match else objective_code
        number = grouped.get(indicator.strategic_objective_id, 0) + 1
        grouped[indicator.strategic_objective_id] = number
        indicator.code = f"{prefix}.{number}"
        indicator.save(update_fields=["code"])


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0004_strategic_objective_indicators")]

    operations = [
        migrations.AddField(
            model_name="strategicobjectiveindicator",
            name="code",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.RunPython(populate_indicator_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="strategicobjectiveindicator",
            name="code",
            field=models.CharField(editable=False, max_length=50),
        ),
    ]
