from django.urls import reverse
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
from django.core.mail import EmailMessage
from django.conf import settings
import os


def send_appraisal_email(request, appraisal, subject, recipient_email, file=None):
    link = request.build_absolute_uri(
        reverse('appraisal_detail', args=[appraisal.id])
    )

    message = f"""
    You have an appraisal task.

    Reference: {appraisal.reference}

    You are by this notification requested to complete and submit your appraisal on or before the deadline {appraisal.date_of_submission}.

    Access here:
    {link}
    """

    email = EmailMessage(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [recipient_email],
    )

    # 🔥 Attach uploaded file (NOT saved in DB)
    if file:
        email.attach(file.name, file.read(), file.content_type)

    email.send(fail_silently=False)


def render_to_pdf(template_src, context_dict):
    template = get_template(template_src)
    html = template.render(context_dict)

    result = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=result,
                                 link_callback=link_callback)

    if not pisa_status.err:
        return result.getvalue()
    return None


def link_callback(uri, rel):
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ""))
    else:
        return uri

    if not os.path.isfile(path):
        raise Exception(f"Media file not found: {path}")

    return path
