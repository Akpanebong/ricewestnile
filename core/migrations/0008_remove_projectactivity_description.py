from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0007_projectactivity_code_description")]

    operations = [
        migrations.RemoveField(
            model_name="projectactivity",
            name="description",
        ),
    ]
