from django import template
from decimal import Decimal

from core.models import CurrencyRate
from core.services import display_amount_from_ugx, format_money, convert_amount, get_user_currency


register = template.Library()


@register.filter
def money(amount, request):
    return format_money(amount, request=request)


@register.filter
def money_plain(amount, request):
    return format_money(amount, request=request, include_equivalent=False)


@register.filter
def accounting_format(amount):
    """
    Format amount with thousand separators (commas) and 2 decimal places.
    Usage in template: {{ amount|accounting_format }}
    """
    if amount is None or amount == '':
        return '0.00'
    
    try:
        num = Decimal(str(amount))
        # Format with commas using Python's format
        return '{:,.2f}'.format(num)
    except (ValueError, TypeError):
        return '0.00'


@register.simple_tag(takes_context=True)
def display_currency(context):
    return get_user_currency(context.get('request'))


@register.simple_tag(takes_context=True)
def convert_ugx(context, amount):
    return convert_amount(
        amount,
        CurrencyRate.UGX,
        get_user_currency(context.get('request')),
    )


@register.simple_tag(takes_context=True)
def money_value(context, amount, source_currency=CurrencyRate.UGX):
    request = context.get('request')
    return format_money(amount, request=request, source_currency=source_currency)


@register.filter
def display_amount(amount, request):
    return display_amount_from_ugx(amount, request=request)


@register.filter
def abs_value(amount):
    """abs() for template use — needed once balances can go negative
    (a signed journal-entry amount putting an account into the opposite
    of its natural position) and the template wants to show the
    magnitude next to a Dr/Cr label rather than a raw negative number."""
    if amount is None:
        return amount
    return abs(amount)


@register.filter
def display_side(amount, natural_side):
    """Given a signed balance and an account's natural side (Dr/Cr from
    FinancialCategory.balance_side), return the side that balance is
    actually sitting on — flips to the opposite of natural_side when the
    balance has gone negative (e.g. a Dr-normal account with more credits
    posted against it than debits). For every pre-existing, always-
    non-negative balance this is a no-op: it just returns natural_side."""
    if amount is None or amount >= 0:
        return natural_side
    return "Cr" if natural_side == "Dr" else "Dr"
