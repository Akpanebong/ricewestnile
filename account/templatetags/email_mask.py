from django import template

register = template.Library()

@register.filter
def mask_email(value):
    if not value or "@" not in value:
        return value

    username, domain = value.split("@")

    # Keep last 2 characters of username
    visible_part = username[-3:] if len(username) >= 3 else username

    return f"***{visible_part}@{domain}"