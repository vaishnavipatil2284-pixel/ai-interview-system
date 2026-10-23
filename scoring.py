def calculate_overall_score(scores):
    """Return the mean score, or 0 if no answers were submitted."""
    if not scores:
        return 0.0
    return round(sum(float(score) for score in scores) / len(scores), 1)
