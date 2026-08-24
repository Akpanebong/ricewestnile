from risk_apps.risk.ml.inference import predict


def calculate_level(score):
    if score >= 20:
        return "VERY HIGH"
    elif score >= 15:
        return "HIGH"
    elif score >= 10:
        return "MODERATE"
    elif score >= 5:
        return "LOW"
    return "VERY LOW"


def compute_risk(likelihood, impact, category):
    if not likelihood or not impact:
        return 0, "LOW", {}, False

    score = likelihood.rating * impact.rating

    ai_level, explanation = predict(
        likelihood.rating,
        impact.rating,
        category.name if category else "Unknown"
    )

    final_level = ai_level or calculate_level(score)
    ai_used = (explanation or {}).get("source") == "model"

    return score, final_level, explanation, ai_used
