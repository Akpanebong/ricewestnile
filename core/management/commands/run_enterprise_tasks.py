from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Run all enterprise management commands in sequence."
    )

    ROUTINE_COMMANDS = (
        "send_staff_monthly_reminders",
        "send_review_reminders",
        "sync_social_media",
        "train_risk_model",
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--continue-on-error",
            action="store_true",
            help="Continue with later commands when one command fails.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the command sequence without executing it.",
        )
        parser.add_argument(
            "--date",
            help="Pass YYYY-MM-DD to send_staff_monthly_reminders.",
        )
        parser.add_argument(
            "--force-social-media",
            action="store_true",
            help="Force configured social-media providers to run.",
        )
        parser.add_argument(
            "--min-records",
            type=int,
            help="Pass the minimum record count to train_risk_model.",
        )
        parser.add_argument(
            "--test-size",
            type=float,
            help="Pass the validation fraction to train_risk_model.",
        )
        parser.add_argument(
            "--random-state",
            type=int,
            help="Pass the random seed to train_risk_model.",
        )

    def handle(self, *args, **options):
        commands = list(self.ROUTINE_COMMANDS)

        self.stdout.write(self.style.MIGRATE_HEADING("Enterprise task sequence"))
        self.stdout.write(" -> ".join(commands))
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: no commands were executed."))
            return

        failures = []
        for position, command_name in enumerate(commands, start=1):
            command_options = self._options_for(command_name, options)
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"[{position}/{len(commands)}] Running {command_name}"
                )
            )
            output, errors = StringIO(), StringIO()
            try:
                call_command(
                    command_name,
                    stdout=output,
                    stderr=errors,
                    **command_options,
                )
            except Exception as exc:
                failures.append((command_name, str(exc)))
                self._write_command_output(output, errors)
                self.stderr.write(self.style.ERROR(f"{command_name} failed: {exc}"))
                if not options["continue_on_error"]:
                    raise CommandError(
                        f"Enterprise task sequence stopped at {command_name}."
                    ) from exc
                continue

            self._write_command_output(output, errors)
            self.stdout.write(self.style.SUCCESS(f"{command_name} completed."))

        if failures:
            summary = "; ".join(f"{name}: {error}" for name, error in failures)
            raise CommandError(f"Enterprise task sequence completed with failures: {summary}")

        self.stdout.write(self.style.SUCCESS("Enterprise task sequence completed successfully."))

    @staticmethod
    def _options_for(command_name, options):
        if command_name == "send_staff_monthly_reminders" and options.get("date"):
            return {"date": options["date"]}
        if command_name == "sync_social_media":
            return {"force": options["force_social_media"]}
        if command_name == "train_risk_model":
            return {
                key: options[key]
                for key in ("min_records", "test_size", "random_state")
                if options.get(key) is not None
            }
        return {}

    def _write_command_output(self, output, errors):
        if output.getvalue():
            self.stdout.write(output.getvalue().rstrip())
        if errors.getvalue():
            self.stderr.write(errors.getvalue().rstrip())
