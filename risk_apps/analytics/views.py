from django.db.models import Avg
from django.views.generic import CreateView, UpdateView, DetailView, ListView, TemplateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from .models import ProgramMetric


class AnalyticsDashboardView(TemplateView):
    template_name = "analytics/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "metric_count": ProgramMetric.objects.count(),
            "avg_budget_utilization": ProgramMetric.objects.aggregate(avg=Avg("budget_utilization"))["avg"] or 0,
            "avg_outcome_score": ProgramMetric.objects.aggregate(avg=Avg("outcome_score"))["avg"] or 0,
            "avg_inclusion_score": ProgramMetric.objects.aggregate(avg=Avg("inclusion_score"))["avg"] or 0,
            "avg_sustainability_score": ProgramMetric.objects.aggregate(avg=Avg("sustainability_score"))["avg"] or 0,
            "recent_metrics": ProgramMetric.objects.all()[:10],
        })
        return context


class ProgramMetricListView(ListView):
    model = ProgramMetric
    template_name = "analytics/metric_list.html"
    context_object_name = "metrics"
    paginate_by = 10


# 🔍 DETAIL VIEW
class ProgramMetricDetailView(DetailView):
    model = ProgramMetric
    template_name = "analytics/detail.html"
    context_object_name = "metric"


# ➕ CREATE
class ProgramMetricCreateView(CreateView):
    model = ProgramMetric
    fields = "__all__"
    exclude = ['created_by']
    template_name = "analytics/form.html"
    success_url = reverse_lazy("program_metric_list")

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.created_by = self.request.user
        messages.success(self.request, "Program Metric created successfully")
        return super().form_valid(form)


# ✏️ UPDATE
class ProgramMetricUpdateView(UpdateView):
    model = ProgramMetric
    fields = "__all__"
    exclude = ['created_by']
    template_name = "analytics/form.html"
    success_url = reverse_lazy("program_metric_list")

    def form_valid(self, form):
        messages.success(self.request, "Program Metric updated successfully")
        return super().form_valid(form)


# 🗑 DELETE (REUSABLE CONFIRMATION)
def program_metric_delete(request, pk):
    metric = get_object_or_404(ProgramMetric, pk=pk)

    if request.method == "POST":
        messages.success(request, f"{metric} deleted successfully.")
        metric.delete()
        return redirect("program_metric_list")

    return render(request, "delete_confirmation.html", {
        "delete": metric,
        "cancel_url": reverse_lazy("metric_detail", kwargs={"pk": metric.pk})
    })