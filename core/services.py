import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

from django.conf import settings
from django.utils import timezone

from .models import CurrencyRate


SUPPORTED_CURRENCIES = (
    CurrencyRate.UGX,
    CurrencyRate.KES,
    CurrencyRate.NGN,
    CurrencyRate.SSP,
    CurrencyRate.USD,
)
CURRENCY_LABELS = {
    CurrencyRate.UGX: 'Ugandan Shilling',
    CurrencyRate.KES: 'Kenyan Shilling',
    CurrencyRate.NGN: 'Nigerian Naira',
    CurrencyRate.SSP: 'South Sudanese Pound',
    CurrencyRate.USD: 'US Dollar',
}
FALLBACK_USD_RATES = {
    CurrencyRate.USD: Decimal('1.000000'),
    CurrencyRate.UGX: Decimal('3700.000000'),
    CurrencyRate.KES: Decimal('129.000000'),
    CurrencyRate.NGN: Decimal('1500.000000'),
    CurrencyRate.SSP: Decimal('130.260000'),
}
RATE_PROVIDER_URL = 'https://open.er-api.com/v6/latest/USD'
CACHE_TTL_SECONDS = 60 * 60 * 12


def normalize_currency(currency):
    currency = (currency or CurrencyRate.UGX).upper()
    return currency if currency in SUPPORTED_CURRENCIES else CurrencyRate.UGX


def get_base_currency():
    """
    The organization's configured base currency — every financial figure
    across the system (FinancialTransaction.amount, requisition items,
    asset values, etc.) is normalized to this, instead of the old hardcoded
    assumption that everything is UGX. Deployments outside Uganda set this
    once (Settings → Currency & Region) to match the region they operate in.
    """
    from .models import OrganizationSettings

    try:
        return normalize_currency(OrganizationSettings.load().base_currency)
    except Exception:
        # Table not migrated yet, DB unreachable, etc. — fail back to the
        # historical default rather than breaking every page that prices
        # something.
        return CurrencyRate.UGX


def get_user_currency(request):
    """
    Resolve the currency to display amounts in. The user's own persisted
    preference (Profile.display_currency) is the single source of truth for
    anyone logged in; the session key is kept only as a fallback for
    anonymous/no-request contexts so this still degrades gracefully.
    """
    currency = getattr(settings, 'DEFAULT_DISPLAY_CURRENCY', None) or get_base_currency()
    if request:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and getattr(user, "display_currency", None):
            currency = user.display_currency
        else:
            currency = request.session.get('display_currency', currency)
    return normalize_currency(currency)


def get_latest_usd_rates(force_refresh=False):
    manual_rates = get_latest_manual_usd_rates()
    if _rates_are_complete(manual_rates):
        return manual_rates

    rates = {}
    for rate in CurrencyRate.objects.filter(
        base_currency=CurrencyRate.USD,
        quote_currency__in=SUPPORTED_CURRENCIES,
    ).order_by('-fetched_at'):
        rates.setdefault(rate.quote_currency, rate)

    rates = {**rates, **manual_rates}

    if not force_refresh and _rates_are_complete(rates) and (_has_manual_rates(rates) or _rates_are_fresh(rates)):
        return rates

    live_rates = fetch_live_usd_rates()
    if live_rates:
        return {**live_rates, **manual_rates}

    if _rates_are_complete(rates):
        return rates

    return create_missing_fallback_rates(rates)


def get_latest_manual_usd_rates():
    rates = {}
    for rate in CurrencyRate.objects.filter(
        base_currency=CurrencyRate.USD,
        quote_currency__in=SUPPORTED_CURRENCIES,
        is_manual=True,
    ).order_by('-rate_date', '-fetched_at'):
        rates.setdefault(rate.quote_currency, rate)
    return rates


def _rates_are_complete(rates):
    return all(currency in rates for currency in SUPPORTED_CURRENCIES)


def _has_manual_rates(rates):
    return any(getattr(rate, 'is_manual', False) for rate in rates.values())


def _rates_are_fresh(rates):
    if not _rates_are_complete(rates):
        return False
    newest_allowed_age = timezone.now() - min(rate.fetched_at for rate in rates.values())
    return newest_allowed_age.total_seconds() < CACHE_TTL_SECONDS


def fetch_live_usd_rates():
    try:
        with urlopen(RATE_PROVIDER_URL, timeout=8) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    fetched_rates = {}
    now = timezone.now()

    for currency in SUPPORTED_CURRENCIES:
        try:
            rate = Decimal(str(payload['rates'][currency]))
        except (KeyError, InvalidOperation, TypeError):
            return None

        if rate <= 0:
            return None

        fetched_rates[currency] = CurrencyRate.objects.create(
            base_currency=CurrencyRate.USD,
            quote_currency=currency,
            rate=rate,
            source=RATE_PROVIDER_URL,
            fetched_at=now,
            rate_date=now.date(),
            is_manual=False,
            is_fallback=False,
        )

    return fetched_rates


def create_missing_fallback_rates(existing_rates=None):
    rates = dict(existing_rates or {})
    for currency in SUPPORTED_CURRENCIES:
        if currency in rates:
            continue
        rates[currency] = CurrencyRate.objects.create(
            base_currency=CurrencyRate.USD,
            quote_currency=currency,
            rate=FALLBACK_USD_RATES[currency],
            source='Fallback configured rate',
            is_manual=False,
            is_fallback=True,
        )
    return rates


def save_manual_usd_rates(rate_values, rate_date, user=None):
    now = timezone.now()
    saved_rates = {}

    for currency in SUPPORTED_CURRENCIES:
        raw_rate = rate_values.get(currency)
        if currency == CurrencyRate.USD and raw_rate in (None, ''):
            raw_rate = '1.000000'
        rate = Decimal(str(raw_rate))
        if rate <= 0:
            raise ValueError(f'{currency} rate must be greater than zero.')

        saved_rates[currency] = CurrencyRate.objects.create(
            base_currency=CurrencyRate.USD,
            quote_currency=currency,
            rate=rate,
            source='Organization manual rate',
            fetched_at=now,
            rate_date=rate_date,
            is_manual=True,
            is_fallback=False,
            input_by=user if getattr(user, 'is_authenticated', False) else None,
        )

    return saved_rates


def build_currency_matrix(rates=None):
    rates = rates or get_latest_usd_rates()
    matrix = []

    for from_currency in SUPPORTED_CURRENCIES:
        row = {
            'currency': from_currency,
            'label': CURRENCY_LABELS[from_currency],
            'values': [],
        }
        for to_currency in SUPPORTED_CURRENCIES:
            row['values'].append({
                'currency': to_currency,
                'amount': convert_amount(1, from_currency, to_currency, rates=rates),
            })
        matrix.append(row)

    return matrix


def get_usd_rate(currency, rates=None):
    currency = normalize_currency(currency)
    rates = rates or get_latest_usd_rates()
    rate_obj = rates.get(currency)
    if rate_obj:
        return rate_obj.rate
    try:
        return FALLBACK_USD_RATES[currency]
    except KeyError:
        return None


def get_usd_ugx_rate(force_refresh=False):
    return get_latest_usd_rates(force_refresh=force_refresh)[CurrencyRate.UGX]


def convert_amount(amount, from_currency, to_currency, rate_obj=None, rates=None):
    from_currency = normalize_currency(from_currency)
    to_currency = normalize_currency(to_currency)

    if amount in (None, ''):
        amount = Decimal('0.00')
    # Strip thousands-separator commas so amounts typed with live formatting
    # (e.g. "1,000,000.00" from a data-currency-input field) parse correctly
    # even if the client-side comma-stripping JS didn't run for some reason.
    if isinstance(amount, str):
        amount = amount.replace(',', '').strip()
    amount = Decimal(str(amount))

    if from_currency == to_currency:
        return quantize_money(amount)

    rates = rates or get_latest_usd_rates()
    from_rate = rate_obj.rate if rate_obj and from_currency == CurrencyRate.UGX else get_usd_rate(from_currency, rates)
    to_rate = rate_obj.rate if rate_obj and to_currency == CurrencyRate.UGX else get_usd_rate(to_currency, rates)

    if not from_rate or not to_rate:
        return quantize_money(amount)

    amount_in_usd = amount / from_rate
    return quantize_money(amount_in_usd * to_rate)


def quantize_money(amount):
    return Decimal(amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def format_money(amount, request=None, source_currency=None, include_equivalent=False):
    # source_currency can't default to get_base_currency() in the signature
    # (defaults are evaluated once at import time, before settings exist) —
    # resolved here instead so a later base-currency change takes effect
    # immediately rather than needing a process restart.
    if source_currency is None:
        source_currency = get_base_currency()
    display_currency = get_user_currency(request)
    rates = get_latest_usd_rates()
    display_amount = convert_amount(amount, source_currency, display_currency, rates=rates)
    primary = f'{display_currency} {display_amount:,.2f}'

    if not include_equivalent:
        return primary

    base_currency = get_base_currency()
    equivalent_currency = CurrencyRate.USD if display_currency != CurrencyRate.USD else base_currency
    equivalent_amount = convert_amount(amount, source_currency, equivalent_currency, rates=rates)
    return f'{primary} ({equivalent_currency} {equivalent_amount:,.2f})'


def display_amount_from_ugx(amount, request=None):
    """
    Despite the name (kept for backward compatibility — it's imported by
    several other apps), this converts from the org's configured base
    currency, not literally UGX, to the viewer's display currency.
    """
    return convert_amount(amount, get_base_currency(), get_user_currency(request))


def user_amount_to_ugx(amount, request=None):
    """
    Despite the name (kept for backward compatibility — it's imported by
    several other apps), this converts to the org's configured base
    currency, not literally UGX, from whatever the viewer's own display
    currency is.
    """
    return convert_amount(amount, get_user_currency(request), get_base_currency())
