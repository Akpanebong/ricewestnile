from account.templatetags.custom_tags import has_group


def is_finance_staff(user):
    """
    Org-wide financial data (the ledger, the chart of accounts, ad-hoc
    transaction recording) is restricted to the same groups the Finance
    dashboard already treats as managers — everyone else only ever sees
    their own requisitions there.
    """
    return user.is_authenticated and (user.is_superuser or has_group(user, "Finance") or has_group(user, "Operations"))


def can_manage_chart_of_accounts(user):
    return user.is_authenticated and (user.is_superuser or has_group(user, "Finance"))
from functools import wraps

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect


def is_finance_editor(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.groups
                                                    .filter(name__iexact="Finance").exists()))


def finance_editor_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        url_name = getattr(getattr(request, "resolver_match", None), "url_name", "") or ""
        is_edit_route = any(action in url_name.lower() for action in ("update", "edit", "delete", "trash"))
        from account.permissions import can_delete_or_trash, can_update_or_edit
        is_delete_route = any(action in url_name.lower() for action in ("delete", "trash"))
        temporary_access = can_delete_or_trash(request.user) if is_delete_route else can_update_or_edit(request.user)
        if not is_finance_editor(request.user) and not (is_edit_route and temporary_access):
            messages.error(request, "Only Finance staff or a superuser can make changes in Finance.")
            return redirect("finance:dashboard")
        return view(request, *args, **kwargs)
    return wrapped


class FinanceEditorRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return is_finance_editor(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "Only Finance staff or a superuser can make changes in Finance.")
        return redirect("finance:dashboard")
