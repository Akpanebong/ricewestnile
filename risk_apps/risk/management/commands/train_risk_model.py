from django.core.management.base import BaseCommand, CommandError

from risk_apps.risk.ml.training import (
    DEFAULT_MIN_RECORDS,
    TrainingDataError,
    TrainingDependencyError,
    train,
)


class Command(BaseCommand):
    help = "Train the risk classification model and write ML artifacts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-records",
            type=int,
            default=DEFAULT_MIN_RECORDS,
            help=f"Minimum labeled risks required for training. Default: {DEFAULT_MIN_RECORDS}.",
        )
        parser.add_argument(
            "--test-size",
            type=float,
            default=0.2,
            help="Fraction of data used for validation. Default: 0.2.",
        )
        parser.add_argument(
            "--random-state",
            type=int,
            default=42,
            help="Random seed for reproducible training. Default: 42.",
        )

    def handle(self, *args, **options):
        try:
            meta = train(
                min_records=options["min_records"],
                test_size=options["test_size"],
                random_state=options["random_state"],
            )
        except (TrainingDependencyError, TrainingDataError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("Risk model trained successfully."))
        self.stdout.write(f"Version: {meta['version']}")
        self.stdout.write(f"Records: {meta['records']}")
        self.stdout.write(f"Accuracy: {meta['accuracy']:.3f}")
        self.stdout.write(f"Metadata: {meta['meta_path']}")
        self.stdout.write(f"Model: {meta['model_path']}")
