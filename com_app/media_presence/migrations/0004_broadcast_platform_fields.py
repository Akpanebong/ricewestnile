from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("media_presence", "0003_alter_newsletter_file"),
    ]

    operations = [
        migrations.RenameField(
            model_name="broadcast",
            old_name="youtube_url",
            new_name="media_url",
        ),
        migrations.RenameField(
            model_name="broadcast",
            old_name="starts_at",
            new_name="published_date",
        ),
        migrations.RemoveField(
            model_name="broadcast",
            name="ends_at",
        ),
        migrations.AddField(
            model_name="broadcast",
            name="media_type",
            field=models.CharField(
                choices=[
                    ("radio", "Radio"),
                    ("television", "Television"),
                    ("podcast", "Podcast"),
                    ("webinar", "Webinar"),
                    ("livestream", "Live stream"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="broadcast",
            name="media_url",
            field=models.URLField(
                help_text="Link to the broadcast on its streaming or media platform",
                validators=[django.core.validators.URLValidator()],
            ),
        ),
        migrations.AlterModelOptions(
            name="broadcast",
            options={"ordering": ("-is_live", "-published_date")},
        ),
    ]
