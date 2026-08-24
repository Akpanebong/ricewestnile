from openpyxl import Workbook
from django.http import HttpResponse


def export_assets_to_excel(queryset):
    wb = Workbook()
    ws = wb.active
    ws.title = "Assets"

    headers = [
        'Asset No', 'Date', 'Category', 'Description',
        'Purchase Value', 'Place', 'Depreciation', 'Net Book Value'
    ]
    ws.append(headers)

    for asset in queryset:
        ws.append([
            asset.asset_no,
            asset.date_of_entry,
            asset.category,
            asset.description,
            asset.purchase_value,
            asset.place,
            asset.depreciation_accumulated,
            asset.net_book_value
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=assets.xlsx'
    wb.save(response)
    return response


def get_client_ip(request):
    """
    Retrieve the real client IP address from the request.
    Works with reverse proxies and load balancers.
    """

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # X-Forwarded-For may contain multiple IPs: client, proxy1, proxy2
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")

    return ip
