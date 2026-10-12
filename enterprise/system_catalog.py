
SYSTEMS = [
    {
        "key": "hr",
        "name": "HR",
        "description": "Employee records, leave, appraisals, recruitment, internships, and exit workflows.",
        "url": "/hr/dashboard/",
        "icon": "fa-users-gear",
    },
    {
        "key": "procurement",
        "name": "Procurement",
        "description": "Procurement plans, suppliers, RFQs, purchase orders, and contracts.",
        "url": "/procurement/",
        "icon": "fa-cart-shopping",
    },
{
        "key": "finance",
        "name": "Accounting",
        "description": "Financial planning, accounting, budgeting, and reporting.",
        "url": "/finance_app/finance/",
        "icon": "fa-coins",
    },
    {
        "key": "mne",
        "name": "M&E",
        "description": "Indicators, monitoring data, reports, resources, locations, and project tracking.",
        "url": "/mne/monitoring/",
        "icon": "fa-chart-line",
    },
    {
        "key": "garcis",
        "name": "GARCIS",
        "description": "Governance, audit, risk, compliance, analytics, and control monitoring.",
        "url": "/garcis/",
        "icon": "fa-shield-halved",
    },
    {
        "key": "governance",
        "name": "Governance",
        "description": "Governance policies, controls, decisions, and stakeholder engagement.",
        "url": "/governance/",
        "icon": "fa-landmark",
    },
    {
        "key": "communication",
        "name": "Communication",
        "description": "Communication planning, reports, presentations, focus areas, and updates.",
        "url": "/communication/",
        "icon": "fa-comments",
    },
    {
        "key": "asset",
        "name": "Assets",
        "description": "Asset registration, tracking, assignments, maintenance, and inventory reporting.",
        "url": "/asset/",
        "icon": "fa-boxes-stacked",
    },
]


def can_view_governance(user):
    """Return whether a user may see and enter the Governance workspace."""
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name__iexact="ED").exists()
            or user.groups.filter(name__iexact="Governance").exists()
        )
    )


def visible_systems(user):
    """Return the system catalogue filtered for the current user."""
    if can_view_governance(user):
        return SYSTEMS
    return [system for system in SYSTEMS if system["key"] != "governance"]
