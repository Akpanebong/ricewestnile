from django.db import migrations, models
import django.db.models.deletion


def move_core_programs_to_program_areas(apps, schema_editor):
    Project = apps.get_model("core", "Project")
    CoreProgram = apps.get_model("core", "CoreProgram")
    ProgramArea = apps.get_model("account", "ProgramArea")

    names = dict(CoreProgram.objects.values_list("id", "name"))
    areas = {}
    for project in Project.objects.exclude(program_area__isnull=True).iterator():
        name = names.get(project.program_area_id)
        if not name:
            continue
        area, _ = ProgramArea.objects.get_or_create(name=name)
        areas[project.program_area_id] = area.pk
        project.program_area_new_id = area.pk
        project.save(update_fields=["program_area_new"])


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0008_profile_forum_last_seen_at"),
        ("core", "0003_alter_resource_resource_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="program_area_new",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="project_migration_records",
                to="account.programarea",
            ),
        ),
        migrations.RunPython(move_core_programs_to_program_areas, migrations.RunPython.noop),
        migrations.RemoveField(model_name="project", name="program_area"),
        migrations.RenameField(model_name="project", old_name="program_area_new", new_name="program_area"),
        migrations.AlterField(
            model_name="project",
            name="program_area",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="projects",
                to="account.programarea",
            ),
        ),
    ]
