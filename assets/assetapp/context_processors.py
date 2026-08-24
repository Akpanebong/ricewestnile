from assets.assetapp.models import Asset


def asset_counts(request):
    return {
        'asset_count': Asset.objects.all()
    }
