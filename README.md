# CounterFlow
**Accessible communication. Shared understanding.**

A multimodal accessibility platform that helps people with disabilities communicate with service staff at hospital reception counters, colleges and government offices.

## Run
```bash
pip install -r requirements.txt
uvicorn main:app --reload          # open http://localhost:8000
pytest                             # backend tests
```
Optional AI (Google Gemini, free via [Google AI Studio](https://aistudio.google.com/apikey)):
```bash
export GEMINI_API_KEY=your_key      # Windows: set GEMINI_API_KEY=your_key
export GEMINI_MODEL=gemini-2.5-flash  # optional; use any free-tier model shown in AI Studio
```
Without a key the rule-based engine runs fully offline.

> **Privacy:** Google states free-tier content may be used to improve its products. Only what the person types or says into the "Tell us what you need" box is sent. For real patients use a paid-tier key or leave Gemini off.

**Try it on two devices:** open the same request number (`#/r/12`) on one device as *the visitor* and another as *staff*. Changes, messages and confirmations sync every 2.5 s. Speech features work best in Chrome/Edge.

## How it maps to the feature list
| Feature | Where |
|---|---|
| AI-assisted clarification, no guessing | `ai.py`: rules extract only explicit statements; ambiguous matches ("appointment or bill") become questions; symptoms never set a department. LLM output is validated (free text must appear in what the person said). |
| Missing-information detection | `services.missing()`; server refuses confirmation while required items are empty |
| Interactive avatar ("Flo") | SVG avatar in `static/app.js`, mouth animates with text-to-speech |
| Sign-language support | 7 sign phrases with avatar poses and written description; real clips in `static/signs/<key>.mp4` take priority. Signs can be sent to the other side, whose avatar plays them |
| Multimodal | typing, quick phrases, browser speech-to-text (en/ta/hi), text-to-speech |
| Personalization | text size, high contrast, read-aloud, language (saved in the browser) |
| Version history & correction | every edit is a new version; original never changes; diff shown per version and original-vs-current |
| Mutual confirmation | both roles must confirm the **same current version**; any edit invalidates earlier confirmations; stale confirms/edits get HTTP 409 |
| Live tracking | status tracker, conversation, staff queue |
| Reusable | add a counter in `services.py` (fields, keywords, phrases) |

## Structure
```
main.py        FastAPI routes + status logic     services.py  counter configs
ai.py          clarification engine              db.py        SQLite schema
static/        index.html, style.css, app.js     tests/       workflow tests
```

## Honest limitations
- The built-in sign poses are a **simple demonstration** of ASL-style signs, not validated sign language. For India use clips recorded or approved by Indian Sign Language users/interpreters, and have Deaf users test the product.
- Browser speech recognition quality varies by language and sends audio to the browser vendor.
- No login: roles are self-selected. Before real deployment add staff authentication, consent notices, data-retention rules, and HTTPS (requests contain personal and health data).
- Polling is used instead of WebSockets for simplicity.
- Never use the tool for emergencies; "Emergency help" is a routing label only.
