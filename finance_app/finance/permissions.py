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
