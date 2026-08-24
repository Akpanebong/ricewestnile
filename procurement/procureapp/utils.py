from io import BytesIO
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from functools import wraps
from django.core.mail import EmailMultiAlternatives
from django.utils.html import format_html
from django.conf import settings
from django.shortcuts import redirect
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
import os


def link_callback(uri, rel):

    # STATIC FILES
    if uri.startswith(settings.STATIC_URL):

        path = os.path.join(
            settings.STATIC_ROOT,
            uri.replace(settings.STATIC_URL, "")
        )

    # MEDIA FILES
    elif uri.startswith(settings.MEDIA_URL):

        path = os.path.join(
            settings.MEDIA_ROOT,
            uri.replace(settings.MEDIA_URL, "")
        )

    else:
        return uri

    if not os.path.isfile(path):
        raise Exception(f"File not found: {path}")

    return path


# for direct download of pdf
def render_pdf(template, ctx, filename, request=None):

    template = get_template(template)
    html = template.render(ctx, request)

    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(src=html, dest=pdf_buffer, encoding='utf-8', link_callback=link_callback)
    if not pisa_status.err:
        pdf_buffer.seek(0)
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    response = HttpResponse(html, content_type='text/html')
    response.write("<hr><strong style='color:red;'>Error generating PDF.</strong><br>")
    response.write(str(pisa_status.err))
    return response


# to save html as pdf in db
def render_pdf_to_bytes(template, ctx):
    """Generate PDF and return raw bytes (not HttpResponse)."""
    template = get_template(template)
    html = template.render(ctx)

    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)
    if pisa_status.err:
        return None
    return pdf_buffer.getvalue()  # ✅ return bytes


def head_of_procurement_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            messages.warning(request, "You are not authorized.")
            return redirect("login")

        # Superuser always allowed
        if user.is_superuser:
            return view_func(request, *args, **kwargs)

        # Department check
        is_operations = (
            hasattr(user, "department")
            and user.department
            and user.department.name.lower() == "operations"
        )

        # Unit check via group
        is_procurement_unit = user.groups.filter(
            name__iexact="Operations - Procurement"
        ).exists()

        if is_operations and is_procurement_unit:
            return view_func(request, *args, **kwargs)

        messages.warning(
            request,
            "Only Procurement Unit staff in Operations Department can access that page."
        )
        return redirect("dashboard")

    return _wrapped_view

def send_html_email(request, subject, recipient, title, message, relative_link=None):
    """
    Sends an HTML + plain text email with an auto-detected domain.

    Args:
        request: Django HttpRequest (to fetch domain automatically)
        subject: Email subject line
        recipient: Recipient email address (string)
        title: Heading/title for the email (displayed in bold)
        message: Body text or instructions
        relative_link: Optional path (e.g. '/procurement/procurements/5/detail/')
    """

    # ✅ Build full domain dynamically
    domain = request.scheme + "://" + request.get_host()
    link = f"{domain}{relative_link}" if relative_link else None

    # ✅ HTML content
    html_body = format_html("""
        <div style="font-family: Arial, sans-serif; line-height: 1.5;">
            <h3 style="color: #007b5e;">{title}</h3>
            <p>{message}</p>
            {link_section}
        </div>
    """,
    title=title,
    message=message,
    link_section=format_html('<p><a href="{}" style="color:#007b5e;">View Details</a></p>', link) if link else "")

    # ✅ Plain text fallback
    text_body = f"{title}\n{message}"
    if link:
        text_body += f"\nView Details: {link}"

    # ✅ Send the email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, "EMAIL_HOST_USER", None),
        to=[recipient],
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=True)
