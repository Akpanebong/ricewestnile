import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
DEFAULT_MIN_RECORDS = 50


class TrainingDependencyError(RuntimeError):
    pass


class TrainingDataError(ValueError):
    pass


def _load_ml_dependencies():
    try:
        import joblib
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score, classification_report
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder, OneHotEncoder
    except ImportError as exc:
        raise TrainingDependencyError(
            "Risk model training requires scikit-learn, joblib, and numpy. "
            "Install them with: pip install scikit-learn joblib numpy"
        ) from exc

    return {
        "joblib": joblib,
        "np": np,
        "RandomForestClassifier": RandomForestClassifier,
        "accuracy_score": accuracy_score,
        "classification_report": classification_report,
        "train_test_split": train_test_split,
        "LabelEncoder": LabelEncoder,
        "OneHotEncoder": OneHotEncoder,
    }


def _create_one_hot_encoder(OneHotEncoder):
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def build_dataset(queryset=None):
    from risk_apps.risk.models import Risk

    risks = queryset or Risk.objects.all()
    risks = (
        risks
        .select_related("likelihood", "impact", "category")
        .exclude(likelihood=None)
        .exclude(impact=None)
        .exclude(risk_level="")
    )

    rows = []

    for risk in risks:
        rows.append({
            "likelihood": risk.likelihood.rating,
            "impact": risk.impact.rating,
            "category": risk.category.name if risk.category else "Unknown",
            "risk_level": risk.risk_level,
        })

    return rows


def train(min_records=DEFAULT_MIN_RECORDS, test_size=0.2, random_state=42):
    deps = _load_ml_dependencies()
    joblib = deps["joblib"]
    np = deps["np"]
    RandomForestClassifier = deps["RandomForestClassifier"]
    accuracy_score = deps["accuracy_score"]
    classification_report = deps["classification_report"]
    train_test_split = deps["train_test_split"]
    LabelEncoder = deps["LabelEncoder"]
    OneHotEncoder = deps["OneHotEncoder"]

    rows = build_dataset()

    if len(rows) < min_records:
        raise TrainingDataError(
            f"Need at least {min_records} labeled risks with likelihood, impact, "
            f"category, and risk_level. Found {len(rows)}."
        )

    class_distribution = Counter(row["risk_level"] for row in rows)

    if len(class_distribution) < 2:
        raise TrainingDataError(
            "Need at least two different risk levels to train a classifier. "
            f"Found: {dict(class_distribution)}."
        )

    X_num = np.array([
        [row["likelihood"], row["impact"]]
        for row in rows
    ])
    X_cat = np.array([
        [row["category"]]
        for row in rows
    ])
    y = np.array([
        row["risk_level"]
        for row in rows
    ])

    cat_encoder = _create_one_hot_encoder(OneHotEncoder)
    X_cat_enc = cat_encoder.fit_transform(X_cat)
    X = np.hstack([X_num, X_cat_enc])

    label_encoder = LabelEncoder()
    y_enc = label_encoder.fit_transform(y)

    can_stratify = min(class_distribution.values()) >= 2
    stratify = y_enc if can_stratify else None

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_enc,
        test_size=test_size,
        stratify=stratify,
        random_state=random_state,
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        class_weight="balanced",
        random_state=random_state,
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    report = classification_report(
        y_test,
        predictions,
        target_names=label_encoder.inverse_transform(sorted(set(y_test))),
        zero_division=0,
        output_dict=True,
    )

    ARTIFACT_DIR.mkdir(exist_ok=True)
    version = f"v{int(datetime.utcnow().timestamp())}"

    model_path = ARTIFACT_DIR / f"model_{version}.pkl"
    label_path = ARTIFACT_DIR / f"label_{version}.pkl"
    cat_path = ARTIFACT_DIR / f"cat_{version}.pkl"
    meta_path = ARTIFACT_DIR / f"meta_{version}.json"

    joblib.dump(model, model_path)
    joblib.dump(label_encoder, label_path)
    joblib.dump(cat_encoder, cat_path)

    meta = {
        "version": version,
        "accuracy": accuracy,
        "records": len(rows),
        "class_distribution": dict(class_distribution),
        "model_path": str(model_path),
        "label_path": str(label_path),
        "cat_path": str(cat_path),
        "report": report,
    }

    with meta_path.open("w") as f:
        json.dump(meta, f, indent=2)

    meta["meta_path"] = str(meta_path)

    return meta


if __name__ == "__main__":
    import os
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "enterprise.settings")
    django.setup()
    print(json.dumps(train(), indent=2))
