from decimal import Decimal

from django import template
from num2words import num2words

from core.models import CurrencyRate
from core.services import convert_amount, format_money, get_user_currency

register = template.Library()


CURRENCY_WORDS = {
    CurrencyRate.UGX: ('Ugandan shilling', 'Ugandan shillings', 'cent', 'cents'),
    CurrencyRate.KES: ('Kenyan shilling', 'Kenyan shillings', 'cent', 'cents'),
    CurrencyRate.NGN: ('Nigerian naira', 'Nigerian naira', 'kobo', 'kobo'),
    CurrencyRate.SSP: ('South Sudanese pound', 'South Sudanese pounds', 'piaster', 'piasters'),
    CurrencyRate.USD: ('US dollar', 'US dollars', 'cent', 'cents'),
}


@register.filter
def has_group(user, group_name):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return user.groups.filter(name=group_name).exists()


@register.filter
def attr(obj, name):
    return getattr(obj, name, '')


@register.filter
def dict_get(value, key):
    try:
        return value.get(key, 0)
    except AttributeError:
        return 0


@register.filter(name='num_to_words')
def num_to_words(value, request=None):
    try:
        if request:
            currency = get_user_currency(request)
            amount = convert_amount(value, CurrencyRate.UGX, currency)
            return money_to_words(amount, currency)
        return num2words(value).capitalize()
    except Exception:
        return value


def money_to_words(value, currency):
    amount = Decimal(str(value or 0)).quantize(Decimal('0.01'))
    major_amount = int(abs(amount))
    minor_amount = int((abs(amount) - Decimal(major_amount)) * 100)
    singular, plural, minor_singular, minor_plural = CURRENCY_WORDS.get(
        currency,
        CURRENCY_WORDS[CurrencyRate.UGX],
    )

    major_unit = singular if major_amount == 1 else plural
    words = f'{num2words(major_amount)} {major_unit}'

    if minor_amount:
        minor_unit = minor_singular if minor_amount == 1 else minor_plural
        words = f'{words} and {num2words(minor_amount)} {minor_unit}'

    if amount < 0:
        words = f'minus {words}'

    return f'{words[:1].upper()}{words[1:]} only'


@register.filter
def money(value, request):
    return format_money(value, request=request)


@register.filter
def money_plain(value, request):
    return format_money(value, request=request, include_equivalent=False)
