from django.conf import settings
from openai import OpenAI
import re

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def transcribe_audio(file_path: str) -> str:
    with open(file_path, "rb") as f:
        res = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=f,
        )
    # docs бойынша json response, негізгі мәтін res.text болуы мүмкін
    return getattr(res, "text", "") or ""



def _normalize(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]+", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s, flags=re.UNICODE)
    return s

def match_keywords(transcript: str, keywords: list[str]) -> list[str]:
    t = _normalize(transcript)
    matched = []

    for kw in (keywords or []):
        if not isinstance(kw, str):
            continue
        k = _normalize(kw)
        if not k:
            continue

        if " " in k:
            if k in t:
                matched.append(kw)
        else:
            if re.search(rf"\b{re.escape(k)}\b", t, flags=re.UNICODE):
                matched.append(kw)

    # unique, original form-да сақтаймыз
    uniq = []
    seen = set()
    for m in matched:
        key = m.strip().lower()
        if key and key not in seen:
            seen.add(key)
            uniq.append(m.strip())
    return uniq

def score_speaking(matched_keywords: list[str], point_per_keyword: int, max_points: int) -> int:
    raw = len(matched_keywords) * int(point_per_keyword or 0)
    cap = int(max_points or 0)
    return min(raw, cap) if cap > 0 else raw
