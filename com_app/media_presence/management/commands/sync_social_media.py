from django.core.management.base import BaseCommand

from com_app.media_presence.sync_services import sync_all


class Command(BaseCommand):
    help = "Fetch Facebook, YouTube, and Twitter/X posts into the Weekly Tracker database."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run configured providers even when global sync is disabled.")

    def handle(self, *args, **options):
        results = sync_all(force=options["force"])
        for result in results:
            message = (
                f"{result['provider']}: {result['status']} | fetched={result['fetched']} "
                f"created={result['created']} updated={result['updated']}"
            )
            if result.get("error"):
                self.stderr.write(self.style.ERROR(message + f" | {result['error']}"))
            else:
                self.stdout.write(self.style.SUCCESS(message))
