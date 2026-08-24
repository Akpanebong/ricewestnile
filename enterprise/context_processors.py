from .system_catalog import SYSTEMS


def system_catalog(request):
    return {"enterprise_systems": SYSTEMS}


def active_system_ui(request):
    namespace = getattr(getattr(request, "resolver_match", None), "namespace", "") or ""
    path = getattr(request, "path", "") or ""

    if namespace == "comm" or path.startswith("/communication/"):
        base_template = "communication/base.html"
    elif namespace == "mne_core" or path.startswith("/mne/"):
        base_template = "mne/base.html"
    elif namespace == "procurement_core" or path.startswith("/procurement/"):
        base_template = "procurement/base.html"
    elif path.startswith("/asset/"):
        base_template = "asset/base.html"
    elif namespace == "garcis" or path.startswith("/garcis/"):
        base_template = "garcis/base.html"
    else:
        base_template = "base.html"

    core_namespace = namespace if namespace in {"mne_core", "procurement_core"} else "mne_core"
    return {
        "active_base_template": base_template,
        "core_url_namespace": core_namespace,
    }
