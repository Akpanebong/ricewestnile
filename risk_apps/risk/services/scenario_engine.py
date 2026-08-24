def analyze_scenario(scenario):

    results = []

    for risk in scenario.risks.select_related("category", "likelihood", "impact"):

        base_score = risk.risk_score or 0
        adjusted_score = base_score * scenario.multiplier

        # Add uncertainty factor
        volatility = getattr(scenario, "volatility", 1.0)
        adjusted_score *= volatility

        # Determine new level
        if adjusted_score >= 20:
            level = "VERY HIGH"
        elif adjusted_score >= 15:
            level = "HIGH"
        elif adjusted_score >= 10:
            level = "MODERATE"
        elif adjusted_score >= 5:
            level = "LOW"
        else:
            level = "VERY LOW"

        results.append({
            "risk": risk,
            "base_score": base_score,
            "adjusted_score": round(adjusted_score, 2),
            "original_level": risk.risk_level,
            "new_level": level,
            "change": adjusted_score - base_score
        })

    return results
