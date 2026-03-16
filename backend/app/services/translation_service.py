"""Lightweight Gemini-based translation helpers for mobile report flow."""

from __future__ import annotations

from app.config import settings

LANGUAGE_LABELS = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "te": "Telugu",
    "mr": "Marathi",
    "ta": "Tamil",
    "ur": "Urdu",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
}


def get_language_label(code: str | None) -> str:
    return LANGUAGE_LABELS.get((code or "en").strip().lower(), "English")


async def translate_text(
    text: str,
    source_language_code: str,
    target_language_code: str,
) -> str:
    """Translate text using Gemini; falls back to original text if translation is unavailable."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    source_code = (source_language_code or "en").strip().lower()
    target_code = (target_language_code or "en").strip().lower()
    if source_code == target_code:
        return cleaned

    source_label = get_language_label(source_code)
    target_label = get_language_label(target_code)

    if not settings.GEMINI_API_KEY:
        return cleaned

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=400,
            ),
            system_instruction="You are a precise translator. Preserve meaning and road-safety context. Return translated text only, no commentary.",
        )

        prompt = (
            f"Translate from {source_label} to {target_label}. "
            f"Keep it concise and natural. Text: {cleaned}"
        )
        response = model.generate_content(prompt)
        translated = (getattr(response, "text", "") or "").strip()
        return translated or cleaned
    except Exception:
        return cleaned
