from django import template

register = template.Library()


@register.filter(name='add_class')
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})


@register.filter
def get_field(form, name):
    return form[name]


@register.filter
def widget_is_textarea(bound_field):
    """Allow templates to identify Django Textarea widgets safely."""
    return bound_field.field.widget.__class__.__name__ == "Textarea"
