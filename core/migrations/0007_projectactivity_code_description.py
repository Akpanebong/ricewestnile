from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0006_projectactivity")]

    operations = [
        migrations.AddField(
            model_name="projectactivity",
            name="code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="projectactivity",
            name="description",
            field=models.TextField(blank=True),
        ),
    ]
