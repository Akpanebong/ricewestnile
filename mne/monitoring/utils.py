import io
import pdfkit
import pandas as pd
from django.http import HttpResponse
from django.template.loader import render_to_string


def apply_filters(qs, params):
    year = params.get('year')
    quarter = params.get('quarter')
    sex = params.get('sex')
    status = params.get('status')
    project_id = params.get('project')
    location_id = params.get('location')
    enterprise_type = params.get("enterprise_type")

    if year:
        qs = qs.filter(year=year)
    if quarter:
        quarter_months = {
            "1": (1, 3),
            "2": (4, 6),
            "3": (7, 9),
            "4": (10, 12),
        }
        month_range = quarter_months.get(str(quarter))
        if month_range:
            qs = qs.filter(month__gte=month_range[0], month__lte=month_range[1])
    if sex:
        qs = qs.filter(sex=sex)
    if status:
        qs = qs.filter(status=status)
    if project_id:
        qs = qs.filter(project_id=project_id)
    if location_id:
        qs = qs.filter(location_id=location_id)
    if enterprise_type:
        qs = qs.filter(enterprise_type=enterprise_type)
    return qs


def generate_excel_from_queryset(qs, filename='data_export.xlsx'):
    """Generate Excel from queryset."""
    rows = []
    for e in qs:
        rows.append({
            'Indicator': getattr(e.indicator, 'name', ''),
            'Project': getattr(e.project, 'name', ''),
            'Donor': getattr(e.project, 'donor', '') if e.project else '',
            'Location': str(e.location) if e.location else '',
            'Year': e.year,
            'Month': e.month,
            'Sex': e.get_sex_display(),
            'Status': e.status,
            'PWD': e.pwd,
            'PWD Nationals': e.pwd_nationals,
            'PWD Refugees': e.pwd_refugees,
            'PWD National Males': e.pwd_national_males,
            'PWD Refugee Males': e.pwd_refugee_males,
            'PWD National Females': e.pwd_national_females,
            'PWD Refugee Females': e.pwd_refugee_females,
            'Enterprise Type': e.enterprise_type,
            'No. of Enterprises': e.no_of_enterprise,
            'No. of Groups reached': e.no_of_group_reached,
            'No. of Group Members': e.no_of_group_members,
            'No. Male': e.no_male,
            'No. Female': e.no_female,
            'Value': e.value,
            'Notes': e.notes,
            'Created At': e.created_at.strftime("%Y-%m-%d %H:%M"),
        })
    df = pd.DataFrame(rows)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    out.seek(0)
    resp = HttpResponse(
        out.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    resp['Content-Disposition'] = f'attachment; filename={filename}'
    return resp


def generate_pdf_from_queryset(qs, filename='data_export.pdf', template='reports/data_pdf.html', context_extra=None):
    """Generate PDF using wkhtmltopdf (pdfkit)."""
    context = {'entries': qs}
    if context_extra:
        context.update(context_extra)

    html = render_to_string(template, context)
    # pdfkit requires wkhtmltopdf installed and in PATH
    options = {
        'enable-local-file-access': None,
        'quiet': ''
    }
    pdf = pdfkit.from_string(html, False, options=options)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response
