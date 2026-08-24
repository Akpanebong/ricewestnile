from django import template
register = template.Library()


@register.filter
def risk_badge(level):
    return {
        "HIGH": "danger",
        "SUBSTANTIAL": "warning",
        "MODERATE": "info",
        "LOW": "success"
    }.get(level, "secondary")


@register.filter
def risk_color(score):
    """
    Return a custom CSS class for risk scores to match the legend colors.
    """
    if score >= 20:
        return "bg-maroon text-white"   # Extreme / Critical
    elif score >= 15:
        return "bg-red text-white"      # High
    elif score >= 10:
        return "bg-orange text-dark"    # Substantial
    elif score >= 5:
        return "bg-yellow text-dark"    # Moderate
    return "bg-success text-white"      # Low / Very Low


@register.filter
def index(sequence, position):
    return sequence[position]


@register.filter
def attr(obj, name):
    value = getattr(obj, name, "")
    if callable(value):
        return value()
    return value
