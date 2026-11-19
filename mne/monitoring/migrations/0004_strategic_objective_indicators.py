from django.db import migrations, models


def move_descriptions_to_indicators(apps, schema_editor):
    StrategicObjective = apps.get_model("monitoring", "StrategicObjective")
    StrategicObjectiveIndicator = apps.get_model("monitoring", "StrategicObjectiveIndicator")
    for objective in StrategicObjective.objects.exclude(description="").iterator():
        StrategicObjectiveIndicator.objects.create(
            strategic_objective_id=objective.pk, indicator=objective.description
        )


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0003_alter_dataentry_value")]
    operations = [
        migrations.CreateModel(
            name="StrategicObjectiveIndicator",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("indicator", models.TextField()),
                ("strategic_objective", models.ForeignKey(
                        on_delete=models.CASCADE,
                    related_name="indicators",
                    to="monitoring.strategicobjective",
                )),
            ],
            options={
                "ordering": ["id"],
                "verbose_name": "Strategic objective indicator",
                "verbose_name_plural": "Strategic objective indicators",
            },
        ),
        migrations.RunPython(move_descriptions_to_indicators, migrations.RunPython.noop),
        migrations.RemoveField(model_name="strategicobjective", name="description"),
    ]
