import json
import os
import re


def _fallback_evaluation(question, answer, reference_answer):
    """Transparent local fallback so the app works without an AI API key."""
    answer_words = set(re.findall(r"[a-zA-Z0-9_]+", answer.lower()))
    reference_words = set(re.findall(r"[a-zA-Z0-9_]+", reference_answer.lower()))
    meaningful = {w for w in reference_words if len(w) > 3}
    overlap = len(answer_words & meaningful) / max(len(meaningful), 1)
    length_factor = min(len(answer.strip()) / 180, 1.0)
    score = round(min(100, max(10, 20 + overlap * 65 + length_factor * 15)))
    strengths = []
    improvements = []
    if overlap >= 0.35:
        strengths.append("Your answer includes several concepts related to the reference answer.")
    else:
        improvements.append("Include more of the key concepts relevant to the question.")
    if len(answer.split()) < 20:
        improvements.append("Add a little more explanation or a concrete example.")
    else:
        strengths.append("Your response provides some explanation.")
    if not improvements:
        improvements.append("Add a practical example to make the answer stronger.")
    return {
        "score": int(score),
        "feedback": "Local keyword-based estimate only. Configure an AI API key for deeper semantic evaluation.",
        "strengths": strengths,
        "improvements": improvements,
        "suggested_answer": reference_answer,
        "evaluation_mode": "fallback"
    }


def evaluate_answer(question, answer, reference_answer, category="General"):
    """Use an OpenAI-compatible API when configured; otherwise use a local fallback."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _fallback_evaluation(question, answer, reference_answer)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL") or None)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        prompt = f"""
You are a constructive interview coach. Evaluate the candidate's answer using the question,
reference answer, and category. Do not reward length alone. For HR questions, assess relevance,
specificity, structure, and reflection rather than technical correctness. Be fair and concise.
Return ONLY valid JSON with this exact schema:
{{
  "score": integer from 0 to 100,
  "feedback": "2-4 sentences",
  "strengths": ["short item", "..."],
  "improvements": ["short item", "..."],
  "suggested_answer": "a clear example of a strong answer"
}}
Category: {category}
Question: {question}
Reference answer / expected concepts: {reference_answer}
Candidate answer: {answer}
"""
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You evaluate interview answers carefully and return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            timeout=45
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        score = max(0, min(100, int(float(data.get("score", 0)))))
        return {
            "score": score,
            "feedback": str(data.get("feedback", "Review the answer and try again."))[:2000],
            "strengths": _clean_list(data.get("strengths")),
            "improvements": _clean_list(data.get("improvements")),
            "suggested_answer": str(data.get("suggested_answer", reference_answer))[:5000],
            "evaluation_mode": "ai"
        }
    except Exception:
        # Avoid breaking the interview if the AI service fails.
        result = _fallback_evaluation(question, answer, reference_answer)
        result["feedback"] = "AI evaluation was unavailable, so a basic local estimate was used. " + result["feedback"]
        result["evaluation_mode"] = "fallback"
        return result


def _clean_list(value):
    if not isinstance(value, list):
        return []
    return [str(item)[:300] for item in value[:8]]
