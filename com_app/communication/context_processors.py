from django.contrib.auth.decorators import login_required
from .models import FocusArea


def focus_areas(request):
    return {'COMM_PROGRAM_AREAS': FocusArea.objects.all()}

