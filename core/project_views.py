from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from account.models import Unit
from core.forms import ProjectForm, ProjectBudgetFormSet
from core.project_models import ProjectBudget, Project


def default_project_budget_rows():
    fiscal_year = ProjectBudget.current_fiscal_year()
    return [
        {'fiscal_year': fiscal_year, 'period': ProjectBudget.FULL_YEAR},
        {'fiscal_year': fiscal_year, 'period': ProjectBudget.Q1},
        {'fiscal_year': fiscal_year, 'period': ProjectBudget.Q2},
        {'fiscal_year': fiscal_year, 'period': ProjectBudget.Q3},
        {'fiscal_year': fiscal_year, 'period': ProjectBudget.Q4},
    ]


# -------------------- PROJECT--------------------
@login_required
def project_list(request):
    fiscal_year = request.GET.get('fiscal_year') or ProjectBudget.current_fiscal_year()
    projects = Project.objects.prefetch_related('budgets')

    for project in projects:
        budgets = [budget for budget in project.budgets.all() if budget.fiscal_year == fiscal_year]
        full_year_budgets = [
            budget for budget in budgets
            if budget.period == ProjectBudget.FULL_YEAR
        ]
        budget_source = full_year_budgets or budgets
        budget_amount = sum((budget.budget_amount for budget in budget_source), 0)
        amount_used = sum((budget.actual_amount_used() for budget in budget_source), 0)
        project.budget_summary = {
            'budget_amount': budget_amount,
            'amount_used': amount_used,
            'amount_remaining': budget_amount - amount_used,
        }

    return render(request, 'project/project_list.html', {
        'projects': projects,
        'fiscal_year': fiscal_year,
    })


@login_required
def project_create(request):
    project = Project.objects.all()
    form = ProjectForm(request.POST or None)
    formset = ProjectBudgetFormSet(
        request.POST or None,
        prefix='budgets',
        initial=default_project_budget_rows() if request.method != 'POST' else None,
    )
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        new_project = form.save()
        formset.instance = new_project
        formset.save()
        messages.success(request, "Project created successfully.")
        return redirect('core:project_list')
    elif request.method != 'POST':
        form = ProjectForm()
        formset = ProjectBudgetFormSet(prefix='budgets', initial=default_project_budget_rows())
    return render(request, 'project/project_form.html', {
        'form': form,
        'formset': formset,
        'project': project,
        'title': 'Create Project',
    })


@login_required
def project_update(request, pk, slug):
    project = get_object_or_404(Project, pk=pk, slug=slug)
    form = ProjectForm(request.POST or None, instance=project)
    formset = ProjectBudgetFormSet(request.POST or None, instance=project, prefix='budgets')
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        messages.success(request, "Project updated successfully.")
        return redirect('core:project_list')
    return render(request, 'project/project_form.html',
                  {
                      'form': form,
                      'formset': formset,
                      'is_update': True,
                      'title': 'Update Project',
                      'project': project,
                  })


@login_required
def project_delete(request, pk, name):
    project = get_object_or_404(Project, pk=pk, name=name)
    if request.method == 'POST':
        project.delete()
        messages.success(request, "Project deleted successfully.")
        return redirect('core:project_list')
    return render(request, 'delete_confirmation.html',
                  {'delete': project, "cancel_url": reverse('core:project_list')})


@login_required
def units_for_department(request):
    units = Unit.objects.filter(department_id=request.GET.get('department')).order_by('name')
    return JsonResponse({'units': [{'id': unit.id, 'name': unit.name} for unit in units]})


@login_required
def projects_for_unit(request):
    projects = Project.objects.filter(unit_id=request.GET.get('unit')).order_by('name')
    return JsonResponse({'projects': [{'id': project.id, 'name': project.name} for project in projects]})
