"""Clarification engine.

Rules first (deterministic, offline, never guesses). If GEMINI_API_KEY (Google AI Studio) is set, Gemini may add
fields the rules missed, but every LLM value is validated against the form and, for free text,
must literally appear in what the person said.
"""
import json
import os
import re
import urllib.request

from services import SERVICES, missing, sub

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")  # any free-tier model listed in Google AI Studio

VAGUE = [
    (r"\b(pain|hurts?|ache|aching)\b",
     r"\b(head|chest|stomach|back|leg|arm|knee|neck|tooth|throat|eye|ear|hand|foot|shoulder|abdomen)\b",
     "Where is the pain? Please write the body part or point to it."),
    (r"\b(not feeling well|unwell|sick|ill)\b", None,
     "Can you tell us in a few words what is wrong?"),
    (r"\b(same as (?:before|last time)|as usual|again|that one)\b", None,
     "Which request do you mean? Please say what you need today."),
]


def _has(low, kw):
    """Whole-word/phrase match, so 'ent' does not match inside 'appointment'."""
    return re.search(r"(?<!\w)" + re.escape(kw.strip()) + r"(?!\w)", low) is not None


def _rules(svc, text):
    low = f" {text.lower()} "
    found, ambiguous = {}, []
    for f in svc["fields"]:
        if f["type"] == "select":
            hits = [(o["v"], kw) for o in f["options"] for kw in o["kw"] if _has(low, kw)]
            # a longer matched keyword (e.g. "not urgent") cancels a shorter one inside it ("urgent")
            hits = [h for h in hits if not any(h[1] != g[1] and h[1] in g[1] and h[0] != g[0] for g in hits)]
            vals = sorted({h[0] for h in hits})
            if len(vals) == 1:
                found[f["key"]] = vals[0]
            elif len(vals) > 1:
                ambiguous.append({"key": f["key"], "options": vals,
                                  "text": "Did you mean " + " or ".join(vals) + "?"})
        elif f.get("rx"):
            m = sub(text, f["rx"])
            if m:
                found[f["key"]] = " ".join(dict.fromkeys(x.strip(" .,;-") for x in m)) if f.get("join") else m[0].strip(" .,;-")
    return found, ambiguous


def _llm(service, svc, text):
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return {}, []
    spec = {f["key"]: [o["v"] for o in f["options"]] if f["type"] == "select" else "free text"
            for f in svc["fields"] if f["key"] != "details"}
    system = ("You extract form fields from what a person with a disability said at a service counter. "
              "ONLY fill a field if the person stated it explicitly. Never infer, diagnose, or guess. "
              'Reply with JSON only: {"fields": {...}, "questions": ["short, simple question"]}.')
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": f"Form fields: {json.dumps(spec)}\nPerson said: {text}"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 400, "responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent", data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            out = json.load(r)["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(re.search(r"\{.*\}", out, re.S).group(0))
    except Exception:
        return {}, []
    fields = {}
    for k, v in (data.get("fields") or {}).items():
        if k not in spec or not isinstance(v, str) or not v.strip():
            continue
        if isinstance(spec[k], list):
            opt = next((o for f in svc["fields"] if f["key"] == k for o in f["options"] if o["v"] == v), None)
            # the choice must be corroborated by the person's own words, not just the model's say-so
            if not opt or not any(_has(text.lower(), w) for w in [v.lower(), *opt["kw"]]):
                continue
        if spec[k] == "free text" and v.lower() not in text.lower():
            continue
        fields[k] = v.strip()
    qs = [q for q in (data.get("questions") or []) if isinstance(q, str)][:2]
    return fields, qs


def analyze(service, text, fields):
    svc = SERVICES[service]
    extracted, ambiguous = _rules(svc, text)
    llm_fields, llm_qs = _llm(service, svc, text)
    for k, v in llm_fields.items():
        extracted.setdefault(k, v)
    # Ambiguous fields are never auto-filled.
    for a in ambiguous:
        extracted.pop(a["key"], None)
    merged = {**fields, **extracted}

    questions = [{"key": a["key"], "text": a["text"], "options": a["options"]} for a in ambiguous]
    asked = {q["key"] for q in questions}
    for pat, part, q in VAGUE:
        if re.search(pat, text, re.I) and not (part and re.search(part, text, re.I)) and not merged.get("details"):
            questions.append({"key": "details", "text": q, "options": []})
            break
    for m in missing(service, merged):
        if m["key"] not in asked:
            questions.append({"key": m["key"], "text": m["ask"], "options": m["options"]})
    for q in llm_qs:
        questions.append({"key": "details", "text": q, "options": []})
    return {"extracted": extracted, "questions": questions, "engine": "rules+llm" if llm_fields or llm_qs else "rules"}
