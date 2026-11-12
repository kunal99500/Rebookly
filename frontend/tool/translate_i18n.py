"""Draft the app's language files from English with the AI, for a fluent speaker to check.

    pip install openai
    set OPENAI_API_KEY=sk-...          (PowerShell: $env:OPENAI_API_KEY="sk-...")
    python tool/translate_i18n.py              # every language, only sentences that are missing
    python tool/translate_i18n.py ta te        # just Tamil and Telugu

* Only missing sentences are translated, so a fluent speaker's corrections are never overwritten.
* Each file is marked "_review": drafts must be checked before release, especially anything about money.
* {placeholders}, amounts, brand names and line breaks are kept exactly; the script refuses a draft that changes them.
"""
import json
import os
import re
import sys
from pathlib import Path

from openai import OpenAI

FOLDER = Path(__file__).resolve().parent.parent / "assets" / "i18n"
LANGUAGES = {
    "hi": "Hindi", "bn": "Bengali", "mr": "Marathi", "ta": "Tamil", "te": "Telugu", "kn": "Kannada", "ml": "Malayalam",
    "gu": "Gujarati", "pa": "Punjabi (Gurmukhi)", "ur": "Urdu", "es": "Spanish (Latin American)", "pt": "Portuguese (Brazilian)",
    "fr": "French", "ar": "Arabic (Modern Standard)", "id": "Indonesian",
}
GUIDE = """You translate the interface of Rebookly, an app for booking local appointments (barbers, salons, tutors, trainers)
with a small deposit that is held on the client's card, not taken, and counts toward their bill.

Rules:
- Plain, warm, everyday language that a shop owner or client with little schooling understands. Short sentences.
- "kept aside" / "held" means the money is reserved on the card but NOT taken. Never translate it as "paid" or "charged".
- Keep exactly as they are: {placeholders}, amounts like ₹80, brand names (Rebookly, PayPal, WhatsApp, Instagram), "QR".
- Keep line breaks (\\n) and non-breaking spaces where they are.
- Times like 4:30 PM may use the local style, but keep the same time.
- Return ONLY a JSON object with the same keys and the translated values."""
MODEL = os.environ.get("TRANSLATE_MODEL", "gpt-5.4-mini")


def placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{\w+\}", text))


def translate(client: OpenAI, language: str, chunk: dict[str, str]) -> dict[str, str]:
    response = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": GUIDE},
                  {"role": "user", "content": f"Translate into {language}:\n{json.dumps(chunk, ensure_ascii=False, indent=1)}"}],
    )
    return json.loads(response.choices[0].message.content)


def main() -> None:
    english = {k: v for k, v in json.loads((FOLDER / "en.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
    client = OpenAI()
    for code in sys.argv[1:] or list(LANGUAGES):
        path = FOLDER / f"{code}.json"
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        missing = {k: v for k, v in english.items() if k not in current}
        print(f"{code}: {len(missing)} to translate")
        keys = list(missing)
        for start in range(0, len(keys), 40):
            chunk = {k: missing[k] for k in keys[start:start + 40]}
            for key, value in translate(client, LANGUAGES[code], chunk).items():
                if key in chunk and placeholders(value) == placeholders(chunk[key]) and value.strip():
                    current[key] = value
                else:
                    print(f"  skipped {key}: the draft changed a placeholder or was empty")
        current["_review"] = f"AI draft ({MODEL}). A fluent {LANGUAGES[code]} speaker must check it before release, especially lines about money."
        ordered = {"_review": current.pop("_review"), **dict(sorted(current.items()))}
        path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
