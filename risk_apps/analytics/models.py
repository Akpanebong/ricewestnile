from django.db import models

from core.models import TimeStampedModel


class ProgramMetric(TimeStampedModel):
    program_name = models.CharField(max_length=255)
    project_name = models.CharField(max_length=255, blank=True)
    metric_date = models.DateField()

    budget_utilization = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    outcome_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    inclusion_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sustainability_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    risk_index = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    compliance_index = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        ordering = ["-metric_date", "program_name"]
        verbose_name = "Program Metric"
        verbose_name_plural = "Program Metrics"

    def __str__(self):
        return f"{self.program_name} - {self.metric_date}"

    @property
    def overall_score(self):
        return round(
            (
                self.budget_utilization +
                self.outcome_score +
                self.inclusion_score +
                self.sustainability_score +
                self.compliance_index
            ) / 5, 2
        )