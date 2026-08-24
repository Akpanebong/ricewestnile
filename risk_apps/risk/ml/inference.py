import os

from .registry import get_latest_meta

try:
    import joblib
    import numpy as np
except ImportError:
    joblib = None
    np = None

MODEL = None
ENCODER = None
META = None
LABEL_ENCODER = None
CAT_ENCODER = None


def fallback_predict(likelihood, impact):
    score = likelihood * impact

    if score >= 20:
        return "VERY HIGH", {"confidence": None, "source": "rule"}
    elif score >= 15:
        return "HIGH", {"confidence": None, "source": "rule"}
    elif score >= 10:
        return "MODERATE", {"confidence": None, "source": "rule"}
    elif score >= 5:
        return "LOW", {"confidence": None, "source": "rule"}
    else:
        return "VERY LOW", {"confidence": None, "source": "rule"}


def load_model():
    global MODEL, LABEL_ENCODER, CAT_ENCODER

    if os.getenv("RISK_AI_ENABLED", "False").lower() != "true":
        return False

    if joblib is None or np is None:
        return False

    meta = get_latest_meta()
    if not meta:
        return False

    MODEL = joblib.load(meta["model_path"])
    LABEL_ENCODER = joblib.load(meta["label_path"])
    CAT_ENCODER = joblib.load(meta["cat_path"])

    return True


def predict(likelihood, impact, category_name):
    if MODEL is None:
        if not load_model():
            return fallback_predict(likelihood, impact)

    try:
        X_num = [[likelihood, impact]]
        X_cat = CAT_ENCODER.transform([[category_name or "Unknown"]])

        X = np.hstack([X_num, X_cat])

        pred = MODEL.predict(X)
        probs = MODEL.predict_proba(X)[0]

        label = LABEL_ENCODER.inverse_transform(pred)[0]

        return label, {
            "confidence": float(max(probs)),
            "source": "model",
        }

    except Exception:
        return fallback_predict(likelihood, impact)
