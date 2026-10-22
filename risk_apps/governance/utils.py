from django.db.models import Q

from account.models import Profile


def governance_reviewers():
    """Return active ED and Governance members who receive review reminders."""
    return Profile.objects.filter(
        Q(groups__name__iexact="ED") | Q(groups__name__iexact="Governance"),
        is_active=True,
    ).distinct()
