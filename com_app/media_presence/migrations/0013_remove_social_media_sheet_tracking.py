from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("media_presence", "0012_socialmediacontent_media_type_and_more")]

    operations = [
        migrations.RemoveField(model_name="socialmediacontent", name="media_type"),
        migrations.RemoveField(model_name="socialmediacontent", name="post_topic"),
        migrations.RemoveField(model_name="socialmediacontent", name="project"),
        migrations.RemoveField(model_name="socialmediacontent", name="scheduled_date"),
        migrations.RemoveField(model_name="socialmediacontent", name="scheduled_time"),
        migrations.RemoveField(model_name="socialmediacontent", name="week_label"),
        migrations.RemoveField(model_name="socialmediacontent", name="source_row"),
        migrations.DeleteModel(name="SocialMediaSheetSource"),
    ]
