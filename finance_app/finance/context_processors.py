def finance_permissions(request):
    try:
        from .permissions import is_finance_staff, can_manage_chart_of_accounts

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return {"is_finance_staff": False, "can_manage_chart_of_accounts": False}

        return {
            "is_finance_staff": is_finance_staff(user),
            "can_manage_chart_of_accounts": can_manage_chart_of_accounts(user),
        }
    except Exception:
        return {"is_finance_staff": False, "can_manage_chart_of_accounts": False}
