from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
from procurement.procureapp.utils import link_callback


def render_to_pdf(template_src, context):
    template = get_template(template_src)
    html = template.render(context)

    result = BytesIO()
    # pisa_status = pisa.CreatePDF(html, dest=result)
    pisa_status = pisa.CreatePDF(src=html, dest=result, encoding='utf-8', link_callback=link_callback)


    if not pisa_status.err:
        return result.getvalue()
    return None

