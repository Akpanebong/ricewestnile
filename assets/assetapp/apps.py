from django.apps import AppConfig


class AssetappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assets.assetapp'
    verbose_name = 'RICE WN Asset Management'


from django.apps import AppConfig

class NgoAssetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assets.ngo_assets'

