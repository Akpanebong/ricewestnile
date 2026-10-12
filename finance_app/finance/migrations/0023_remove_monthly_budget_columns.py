from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("finance", "0022_restore_legacy_monthly_compatibility_fields")]

    operations = [
        migrations.RemoveField(model_name="financebudgetline", name=f"m{i:02d}")
        for i in range(1, 13)
    ]
