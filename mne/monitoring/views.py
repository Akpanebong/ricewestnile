from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.views.generic import ListView
from account.utils import MealTeamAccessMixin
from .forms import DataEntryForm
import csv, io
from django.db.models import Min, Max, Count, Sum, Q
from django.contrib import messages
from django.urls import reverse
from .utils import apply_filters, generate_excel_from_queryset, generate_pdf_from_queryset
from .models import StrategicObjective, Output, Indicator, DataEntry, Project, Location, CoreProgram
from django.utils.timezone import now
from django.db.models.functions import Coalesce
from account.utils import superuser_required, meal_team_required
from .forms import IndicatorForm, OutputForm, StrategicObjectiveForm

QUARTERS = [
    ("1", "Q1 (Jan-Mar)"),
    ("2", "Q2 (Apr-Jun)"),
    ("3", "Q3 (Jul-Sep)"),
    ("4", "Q4 (Oct-Dec)"),
]


def _monitoring_route(request, name):
    namespace = getattr(getattr(request, "resolver_match", None), "namespace", "") or "monitoring"
    if namespace != "monitoring":
        namespace = "monitoring"
    return f"{namespace}:{name}"


def _dashboard_params(request):
    params = request.GET.copy()
    if not params.get("year"):
        params["year"] = str(now().year)
    return params


def _total_people(qs):
    totals = qs.aggregate(
        male=Coalesce(Sum("no_male"), 0),
        female=Coalesce(Sum("no_female"), 0),
    )
    return (totals["male"] or 0) + (totals["female"] or 0)


def _pwd_total(qs):
    totals = _pwd_breakdown(qs)
    return sum(totals.values())


def _pwd_breakdown(qs):
    fields = [
        "pwd_nationals",
        "pwd_refugees",
        "pwd_national_males",
        "pwd_refugee_males",
        "pwd_national_females",
        "pwd_refugee_females",
    ]
    return qs.aggregate(**{field: Coalesce(Sum(field), 0) for field in fields})


def _dashboard_metrics(qs):
    refugee_totals = qs.filter(status="Refugee").aggregate(
        male=Coalesce(Sum("no_male"), 0),
        female=Coalesce(Sum("no_female"), 0),
    )
    national_totals = qs.filter(status="National").aggregate(
        male=Coalesce(Sum("no_male"), 0),
        female=Coalesce(Sum("no_female"), 0),
    )

    refugee_male = refugee_totals["male"] or 0
    refugee_female = refugee_totals["female"] or 0
    national_male = national_totals["male"] or 0
    national_female = national_totals["female"] or 0
    pwd_breakdown = _pwd_breakdown(qs)

    return {
        "refugee_male": refugee_male,
        "refugee_female": refugee_female,
        "national_male": national_male,
        "national_female": national_female,
        "refugee_total": refugee_male + refugee_female,
        "national_total": national_male + national_female,
        "total_male": refugee_male + national_male,
        "total_female": refugee_female + national_female,
        "pwd_total": sum(pwd_breakdown.values()),
        **pwd_breakdown,
    }


@meal_team_required(allow_other_departments=True) # MEAL + superusers + other departments allowed
def dashboard(request):

    current_year = now().year
    filter_params = _dashboard_params(request)

    # ===============================
    # BASIC COUNTS
    # ===============================
    total_so = StrategicObjective.objects.count()
    total_outputs = Output.objects.count()
    total_indicators = Indicator.objects.count()

    projects = Project.objects.all()
    locations = Location.objects.all()

    filtered_entries = apply_filters(DataEntry.objects.select_related("project", "location"), filter_params)

    project_groups_qs = (
    filtered_entries
    .values("project__name")
    .annotate(
        groups_total=Coalesce(Sum("no_of_group_reached"), 0)
    )
    .order_by("project__name")
    )

    project_labels = [i["project__name"] for i in project_groups_qs]
    project_groups = [i["groups_total"] for i in project_groups_qs]

    # ===============================
    # YEAR RANGE
    # ===============================
    year_range = DataEntry.objects.aggregate(
        min_y=Min("year"),
        max_y=Max("year")
    )

    min_year = year_range["min_y"] or current_year
    max_year = year_range["max_y"] or current_year
    years = range(min_year, max_year + 1)

    metrics = _dashboard_metrics(filtered_entries)

    # ===============================
    # YEARLY TREND
    # ===============================
    yearly_trend = (
        filtered_entries
        .values("year")
        .annotate(
            male=Coalesce(Sum("no_male"), 0),
            female=Coalesce(Sum("no_female"), 0),
        )
        .order_by("year")
    )

    yearly_labels = [str(i["year"]) for i in yearly_trend]
    yearly_totals = [(i["male"] or 0) + (i["female"] or 0) for i in yearly_trend]

    # ===============================
    # ENTERPRISE TYPE
    # ===============================
    enterprise_qs = (
        filtered_entries
        .values("enterprise_type")
        .annotate(
            national_male=Coalesce(Sum("no_male", filter=Q(status="National")), 0),
            national_female=Coalesce(Sum("no_female", filter=Q(status="National")), 0),
            refugee_male=Coalesce(Sum("no_male", filter=Q(status="Refugee")), 0),
            refugee_female=Coalesce(Sum("no_female", filter=Q(status="Refugee")), 0),
        )
        .order_by("enterprise_type")
    )

    enterprise_labels = [i["enterprise_type"] for i in enterprise_qs]
    enterprise_national = [(i["national_male"] or 0) + (i["national_female"] or 0) for i in enterprise_qs]
    enterprise_refugee = [(i["refugee_male"] or 0) + (i["refugee_female"] or 0) for i in enterprise_qs]

    context = {

        "years": years,
        "quarters": QUARTERS,
        "selected_filters": filter_params,
        "projects": projects,
        "locations": locations,
        "project_labels": project_labels,
        "project_groups": project_groups,

        "total_so": total_so,
        "total_outputs": total_outputs,
        "total_indicators": total_indicators,

        "current_year": current_year,

        **metrics,

        "enterprise_types": DataEntry._meta.get_field("enterprise_type").choices,

        "yearly_labels": yearly_labels,
        "yearly_totals": yearly_totals,

        "enterprise_labels": enterprise_labels,
        "enterprise_national": enterprise_national,
        "enterprise_refugee": enterprise_refugee,
    }

    return render(request, "mne/dashboard.html", context)


@meal_team_required() # Only users in MEAL group + superusers can access
def data_entry_list(request):
    recent_entries = DataEntry.objects.select_related('indicator', 'project', 'location').order_by('-created_at')
    return render(request, 'indicators/entry_data_list.html', {"recent_entries": recent_entries})


@superuser_required
def update_data_entry(request, pk):
    data = get_object_or_404(DataEntry, pk=pk)

    if request.method == 'POST':
        form = DataEntryForm(request.POST, request.FILES, instance=data)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.indicator = data.indicator
            entry.save()

            messages.success(request, f"Data: {data} updated successfully.")
            return redirect('monitoring:data_entry_list')
    else:
        form = DataEntryForm(instance=data)

    return render(
        request,
        'entry_form.html',
        {
            'form': form,
            'is_update': True,
            'indicator': data.indicator,
            'data': data,
            'title': f'Update {data}',
            'form_action': reverse('monitoring:update_data_entry', args=[data.pk]),
        }
    )


@meal_team_required() # Only users in MEAL group + superusers can access
def entry_form(request, indicator_id):
    indicator = get_object_or_404(Indicator, pk=indicator_id)

    if request.method == 'POST':
        form = DataEntryForm(request.POST, request.FILES)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.indicator = indicator
            entry.created_by = request.user
            entry.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'entry_id': entry.pk})

            messages.success(request, "Data entry saved successfully.")
            return redirect(reverse('monitoring:data_entry_list'))

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(
                request,
                'entry_form.html',
                {
                    'form': form,
                    'indicator': indicator,
                    'form_action': reverse('monitoring:entry_form', args=[indicator.pk]),
                },
                status=400
            )

    # GET request (display form)
    init = {'indicator': indicator}
    for field in [
        'project', 'location', 'year', 'sex', 'status', 'pwd', 'enterprise_type',
        'pwd_nationals', 'pwd_refugees', 'pwd_national_males', 'pwd_refugee_males',
        'pwd_national_females', 'pwd_refugee_females',
    ]:
        if request.GET.get(field):
            init[field] = request.GET.get(field)
    form = DataEntryForm(initial=init)

    return render(
        request,
        'entry_form.html',
        {
            'form': form,
            'indicator': indicator,
            'form_action': reverse('monitoring:entry_form', args=[indicator.pk]),
        },
    )



def chart_data(request):
    chart_type = request.GET.get('type', 'sex')
    qs = DataEntry.objects.select_related("project", "location")
    qs = apply_filters(qs, request.GET)

    if chart_type == "summary":
        return JsonResponse(_dashboard_metrics(qs))

    if not qs.exists():
        return JsonResponse({'labels': [], 'values': []})

    # ===============================
    # SEX
    # ===============================

    if chart_type == "sex":

        data = qs.values("status").annotate(
            male=Coalesce(Sum("no_male"), 0),
            female=Coalesce(Sum("no_female"), 0)
        )

        labels = []
        values = []

        for d in data:
            labels.append(f"Male ({d['status']})")
            values.append(d["male"])

            labels.append(f"Female ({d['status']})")
            values.append(d["female"])

        return JsonResponse({
            "labels": labels,
            "values": values
        })

    # ===============================
    # STATUS
    # ===============================
    elif chart_type == 'status':

        data = qs.values('status').annotate(
            male=Coalesce(Sum('no_male'),0),
            female=Coalesce(Sum('no_female'),0)
        )

        labels = [d['status'] for d in data]
        values = [d['male'] + d['female'] for d in data]

        return JsonResponse({
            'labels': labels,
            'values': values
        })

    # ===============================
    # PWD
    # ===============================
    if chart_type == "pwd":
        pwd_total = _pwd_total(qs)
        members_total = _total_people(qs)

        non_pwd = max(members_total - pwd_total, 0)

        return JsonResponse({
            "labels": ["PWD", "Non-PWD"],
            "values": [pwd_total, non_pwd]
        })

    # ===============================
    # LOCATION
    # ===============================
    elif chart_type == 'location':
        data = qs.values('location__district').annotate(total=Count('id'))
        labels = [d['location__district'] or 'N/A' for d in data]
        values = [d['total'] for d in data]
        return JsonResponse({'labels': labels, 'values': values})

    # ===============================
    # PROJECT
    # ===============================
    elif chart_type == "project_groups":

        qs = qs.values("project__name").annotate(
            total=Coalesce(Sum("no_of_group_reached"),0)
        ).order_by("project__name")

        labels = [i["project__name"] or "Unknown" for i in qs]
        values = [i["total"] for i in qs]

        return JsonResponse({
            "labels": labels,
            "values": values
        })

    # ===============================
    # 🔵 YEARLY TREND (FILTER RESPONSIVE)
    # ===============================
    elif chart_type == 'yearly_trend':
        data = (
            qs.values('year')
            .annotate(
                male=Coalesce(Sum('no_male'), 0),
                female=Coalesce(Sum('no_female'), 0),
            )
            .order_by('year')
        )

        labels = [str(d['year']) for d in data]
        values = [(d['male'] or 0) + (d['female'] or 0) for d in data]

        return JsonResponse({'labels': labels, 'values': values})

    # ===============================
    # 🟢 ENTERPRISE TYPE (STACKED)
    # ===============================
    elif chart_type == 'enterprise_type':
        data = (
            qs.values('enterprise_type')
            .annotate(
                national_male=Coalesce(Sum('no_male', filter=Q(status='National')), 0),
                national_female=Coalesce(Sum('no_female', filter=Q(status='National')), 0),
                refugee_male=Coalesce(Sum('no_male', filter=Q(status='Refugee')), 0),
                refugee_female=Coalesce(Sum('no_female', filter=Q(status='Refugee')), 0),
            )
            .order_by('enterprise_type')
        )

        labels = [d['enterprise_type'] or "Unknown" for d in data]
        national = [(d['national_male'] or 0) + (d['national_female'] or 0) for d in data]
        refugee = [(d['refugee_male'] or 0) + (d['refugee_female'] or 0) for d in data]

        return JsonResponse({
            'labels': labels,
            'national': national,
            'refugee': refugee
        })

    # ===============================
    # DEFAULT ENTERPRISE (COUNT)
    # ===============================
    else:
        data = qs.values('enterprise_type').annotate(total=Count('id'))
        labels = [d['enterprise_type'] for d in data]
        values = [d['total'] for d in data]
        return JsonResponse({'labels': labels, 'values': values})


@meal_team_required() # Only users in MEAL group + superusers can access
def hierarchy_view(request):
    total_outputs = Output.objects.count()
    total_indicators = Indicator.objects.count()
    sos = StrategicObjective.objects.prefetch_related('outputs__indicators').all()
    return render(request, 'hierarchy.html', {'sos': sos, 'total_outputs': total_outputs, 'total_indicators': total_indicators})


@require_GET
def ajax_outputs_for_so(request, so_id):
    """
    Returns all Outputs for a given Strategic Objective, including:
    - id, code, title (original keys)
    - indicators_count (new)
    - color (optional, defaults to theme color)
    """
    so = get_object_or_404(StrategicObjective, pk=so_id)

    # Prefetch indicators for performance
    outputs = (
        so.outputs
            .prefetch_related('indicators')
            .annotate(indicators_count=Count('indicators'))
    )

    data = {
        'outputs': [
            {
                'id': o.id,
                'code': o.code,
                'title': o.title,
                'color': getattr(o, 'color', '#10b981'),  # fallback green
                'indicators_count': o.indicators_count or 0,
            }
            for o in outputs
        ]
    }

    return JsonResponse(data)


@require_GET
def ajax_indicators_for_output(request, output_id):
    output = get_object_or_404(Output, pk=output_id)
    indicators = [{'id': i.id, 'code': i.code, 'name': i.name} for i in output.indicators.all()]
    return JsonResponse({'indicators': indicators})


@meal_team_required() # Only users in MEAL group + superusers can access
def core_program_list(request):
    programs = CoreProgram.objects.all().order_by("name")
    current_year = now().year
    return render(request, "core_program_list.html", {
        "programs": programs,  "year": current_year
    })


def core_program_chart(request, pk):

    program = get_object_or_404(CoreProgram, pk=pk)

    data = DataEntry.objects.filter(program_area=program, year=now().year)

    reached = data.aggregate(total=Sum("no_of_group_members"))["total"] or 0
    target = data.aggregate(total=Sum("value"))["total"] or 0



    achievement = 0
    if target > 0:
        achievement = round((reached / target) * 100, 1)

    return JsonResponse({
        "program": program.name,
        "reached": reached,
        "target": target,
        "achievement": achievement,

    })


@meal_team_required(allow_other_departments=True) # MEAL + superusers + other departments allowed
def export_excel(request):
    """Export filtered data as Excel (from dashboard filters)."""
    qs = apply_filters(DataEntry.objects.select_related('indicator', 'project', 'location'), request.GET)
    return generate_excel_from_queryset(qs, filename='M_E_Data.xlsx')


@meal_team_required(allow_other_departments=True) # MEAL + superusers + other departments allowed
def export_pdf(request):
    """Export filtered data as PDF."""
    qs = apply_filters(DataEntry.objects.select_related('indicator', 'project', 'location'), request.GET)
    return generate_pdf_from_queryset(qs, filename='M_E_Data.pdf', template='reports/data_pdf.html')


@meal_team_required(allow_other_departments=True)
def export_indicator_excel(request, pk):
    indicator = get_object_or_404(Indicator, pk=pk)
    qs = DataEntry.objects.select_related('indicator', 'project', 'location').filter(indicator=indicator)
    return generate_excel_from_queryset(qs, filename=f'{indicator.code}_Data.xlsx')


@meal_team_required(allow_other_departments=True)
def export_indicator_pdf(request, pk):
    indicator = get_object_or_404(Indicator, pk=pk)
    qs = DataEntry.objects.select_related('indicator', 'project', 'location').filter(indicator=indicator)
    return generate_pdf_from_queryset(
        qs,
        filename=f'{indicator.code}_Data.pdf',
        template='reports/indicator_pdf.html',
        context_extra={'indicator': indicator},
    )


@meal_team_required()
def download_csv_template(request):
    headers = [
        'indicator_code', 'project_code', 'district', 'program_area', 'sub_county', 'settlement',
        'year', 'month', 'sex', 'status', 'pwd', 'pwd_nationals', 'pwd_refugees',
        'pwd_national_males', 'pwd_refugee_males', 'pwd_national_females',
        'pwd_refugee_females', 'enterprise_type', 'no_of_enterprise',
        'no_of_group_reached', 'no_of_group_members', 'no_male', 'no_female',
        'value', 'notes'
    ]
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=MEAL_Data_Import_Template.csv'
    writer = csv.writer(response)
    writer.writerow(headers)
    return response



@meal_team_required() # Only users in MEAL group + superusers can access
def csv_import(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        raw = request.FILES['csv_file'].read()

        # Try multiple encodings
        for enc in ['utf-8', 'latin-1', 'cp1252', 'utf-16']:
            try:
                data = raw.decode(enc)
                break
            except UnicodeDecodeError:
                data = None

        if data is None:
            messages.error(request, "Unable to decode CSV. Please save the file as UTF-8.")
            return redirect('monitoring:csv_import')

        # Remove binary NULL characters
        data = data.replace('\x00', '')

        reader = csv.DictReader(io.StringIO(data))
        created = 0
        errors = []

        def int_from_row(row, key, default=0):
            value = row.get(key, default)
            if value in [None, ""]:
                return default
            return int(value)

        for nr, row in enumerate(reader, start=1):
            try:
                ind = Indicator.objects.get(code=row['indicator_code'].strip())

                project = None
                if row.get('project_code'):
                    project = Project.objects.filter(code=row['project_code'].strip()).first()

                loc = None
                if row.get('district'):
                    loc, _ = Location.objects.get_or_create(
                        district=row['district'].strip(),
                        sub_county=row.get('sub_county', '').strip(),
                        settlement=row.get('settlement', '').strip()
                    )

                DataEntry.objects.create(
                    indicator=ind,
                    project=project,
                    location=loc,
                    year=int_from_row(row, 'year'),
                    month=int_from_row(row, 'month') or None,
                    sex=row.get('sex', 'M'),
                    status=row.get('status', 'National'),
                    pwd=int_from_row(row, 'pwd'),
                    pwd_nationals=int_from_row(row, 'pwd_nationals'),
                    pwd_refugees=int_from_row(row, 'pwd_refugees'),
                    pwd_national_males=int_from_row(row, 'pwd_national_males'),
                    pwd_refugee_males=int_from_row(row, 'pwd_refugee_males'),
                    pwd_national_females=int_from_row(row, 'pwd_national_females'),
                    pwd_refugee_females=int_from_row(row, 'pwd_refugee_females'),
                    enterprise_type=row.get('enterprise_type', 'Other'),
                    no_of_enterprise=int_from_row(row, 'no_of_enterprise') or None,
                    no_of_group_reached=int_from_row(row, 'no_of_group_reached') or None,
                    no_of_group_members=int_from_row(row, 'no_of_group_members') or None,
                    no_male=int_from_row(row, 'no_male') or None,
                    no_female=int_from_row(row, 'no_female') or None,
                    value=float(row.get('value') or 0),
                    notes=row.get('notes', ''),
                )
                created += 1

            except Exception as e:
                errors.append(f"Row {nr}: {e}")

        messages.info(request, f"Imported {created} rows; {len(errors)} errors")
        return render(request, "csv_import_result.html", {"created": created, "errors": errors})

    return render(request, "csv_import.html")



class SoListView(MealTeamAccessMixin, ListView):
    model = StrategicObjective
    template_name = "indicators/so_list.html"
    paginate_by = 25
    context_object_name = "so_list"
    ordering = ["code"]


@meal_team_required(allow_other_departments=True)
def so_detail(request, pk, title):
    so = get_object_or_404(StrategicObjective, pk=pk, title=title)
    return render(request, "indicators/so_detail.html", {"so": so, "output": Output.objects.filter(so=so)})


@superuser_required
def create_so(request):
    form = StrategicObjectiveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Strategic objective created.")
        return redirect(_monitoring_route(request, "so_list"))
    return render(request, "indicators/create_so.html", {"form": form})


@superuser_required
def update_so(request, title, pk):
    so = get_object_or_404(StrategicObjective, title=title, pk=pk)
    form = StrategicObjectiveForm(request.POST or None, instance=so)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Strategic objective updated.")
        return redirect(_monitoring_route(request, "so_list"))
    return render(request, "indicators/create_so.html", {"form": form, "is_update": True, "so": so})


@superuser_required
def trash_so(request, pk, title):
    so = get_object_or_404(StrategicObjective, pk=pk, title=title)
    if request.method == "POST":
        so.delete()
        messages.success(request, "Strategic objective deleted.")
        return redirect(_monitoring_route(request, "so_list"))
    return render(request, "delete_confirmation.html", {"delete": so, "cancel_url": reverse(_monitoring_route(request, "so_list"))})


@superuser_required
def create_output(request, so_id):
    so = get_object_or_404(StrategicObjective, pk=so_id)
    form = OutputForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        output = form.save(commit=False)
        output.so = so
        output.save()
        messages.success(request, "Output created.")
        return redirect(_monitoring_route(request, "so_detail"), pk=so.pk, title=so.title)
    return render(request, "indicators/create_output.html", {"form": form, "so": so, "output": Output.objects.filter(so=so)})


@superuser_required
def update_output(request, title, pk):
    output = get_object_or_404(Output, title=title, pk=pk)
    form = OutputForm(request.POST or None, instance=output)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Output updated.")
        return redirect(_monitoring_route(request, "so_detail"), pk=output.so.pk, title=output.so.title)
    return render(request, "indicators/create_output.html", {"form": form, "is_update": True, "output": output})


@superuser_required
def trash_output(request, pk, title):
    output = get_object_or_404(Output, pk=pk, title=title)
    if request.method == "POST":
        so = output.so
        output.delete()
        messages.success(request, "Output deleted.")
        return redirect(_monitoring_route(request, "so_detail"), pk=so.pk, title=so.title)
    return render(request, "delete_confirmation.html", {"delete": output, "cancel_url": reverse(_monitoring_route(request, "so_list"))})


@meal_team_required()
def output_detail(request, pk, title):
    output = get_object_or_404(Output, pk=pk, title=title)
    return render(request, "indicators/output_detail.html", {"output": output, "indicator": Indicator.objects.filter(output=output)})


class OutputListView(MealTeamAccessMixin, ListView):
    model = Output
    template_name = "indicators/output_list.html"
    paginate_by = 25
    context_object_name = "output_list"
    ordering = ["code"]


class IndicatorListView(MealTeamAccessMixin, ListView):
    model = Indicator
    template_name = "indicators/indicator_list.html"
    paginate_by = 25
    context_object_name = "indicator_list"
    ordering = ["code"]


@meal_team_required()
def indicator_detail(request, pk):
    indicator = get_object_or_404(Indicator, pk=pk)
    entries = indicator.entries.select_related("location", "project").all()
    return render(request, "indicators/indicator_detail.html", {"indicator": indicator, "entries": entries})


@superuser_required
def create_indicator(request, output_id):
    output = get_object_or_404(Output, pk=output_id)
    form = IndicatorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        indicator = form.save(commit=False)
        indicator.output = output
        indicator.save()
        messages.success(request, "Indicator created.")
        return redirect(_monitoring_route(request, "output_detail"), pk=output.pk, title=output.title)
    return render(request, "indicators/create_indicator.html", {"form": form, "output": output})


@superuser_required
def update_indicator(request, name, pk):
    indicator = get_object_or_404(Indicator, name=name, pk=pk)
    output = indicator.output
    form = IndicatorForm(request.POST or None, instance=indicator)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Indicator updated.")
        return redirect(_monitoring_route(request, "indicator_list"))
    return render(request, "indicators/create_indicator.html", {"form": form, "is_update": True,
                                                                "indicator": indicator, "output": output})


@superuser_required
def trash_indicator(request, pk, name):
    indicator = get_object_or_404(Indicator, pk=pk, name=name)
    if request.method == "POST":
        indicator.delete()
        messages.success(request, "Indicator deleted.")
        return redirect(_monitoring_route(request, "indicator_list"))
    return render(request, "delete_confirmation.html", {"delete": indicator, "cancel_url": reverse(_monitoring_route(request, "indicator_list"))})
