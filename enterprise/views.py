from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .system_catalog import visible_systems


@login_required
def system_home(request):
    return render(request, "enterprise/system_home.html", {"systems": visible_systems(request.user)})
