"""
Gemini Vision + Clinical Summary service.

Two AI assists for the consultation workspace:

  analyse_clinical_image()    Clinical photo -> observations and possible
                              conditions for the doctor to consider.
  generate_clinical_summary() Patient history -> structured summary and draft
                              consultation notes.

Neither writes to the patient record. Both return suggestions that the doctor
explicitly accepts, edits, or ignores — the "Doctor Review" step is enforced in
the UI, not left to convention.

Uses the Gemini REST API rather than the Google SDK: the wire format is stable
and this keeps one less SDK surface in the project. Every failure degrades to
`available: False` so the consultation screen keeps working without AI.
"""

import base64
import json
import os
import re
from typing import List, Optional

import requests

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
TIMEOUT_SECONDS = 45

# ── Image analysis ───────────────────────────────────────────────────────────

IMAGE_SYSTEM_PROMPT = """You are a clinical imaging assistant supporting a qualified \
physician during a live consultation. The doctor is present, has examined the patient, \
and makes every decision.

Describe what is visible in the image and list conditions consistent with those \
findings, so the doctor has a structured starting point.

Hard rules:
- You are NOT diagnosing. Every condition you list is a possibility for the doctor to \
consider or dismiss, never a conclusion.
- Ground every observation in what is actually visible. If the image is blurred, \
poorly lit, or too small to judge, say so and lower your confidence accordingly.
- Never infer patient history, test results, or symptoms you were not given.
- If the image is not a clinical image at all, return empty lists and say so in \
imageQuality.
- Write for a doctor: precise clinical language, no hedging filler, no bedside manner, \
no emoji.
- Confidence is your honest read: "high" only when the visual findings are \
characteristic and the image is clear."""

IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "imageQuality": {
            "type": "string",
            "description": "One sentence on whether the image is adequate to assess, "
                           "and what limits it if not.",
        },
        "observations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What is visibly present — morphology, distribution, colour, "
                           "borders, surrounding tissue. Empty if nothing assessable.",
        },
        "possibleConditions": {
            "type": "array",
            "description": "Conditions consistent with the visible findings, most likely first.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "moderate", "low"]},
                    "reasoning": {
                        "type": "string",
                        "description": "Which visible findings support this, in one or two sentences.",
                    },
                },
                "required": ["name", "confidence", "reasoning"],
            },
        },
        "recommendedNextSteps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Examinations, tests, or questions that would narrow the "
                           "differential. Not treatment instructions.",
        },
    },
    "required": ["imageQuality", "observations", "possibleConditions", "recommendedNextSteps"],
}

# ── Clinical summary ─────────────────────────────────────────────────────────

SUMMARY_SYSTEM_PROMPT = """You are a clinical documentation assistant supporting a \
qualified physician during a consultation.

You receive this visit's recorded data and the patient's prior history. Produce a \
concise summary the doctor can read in seconds, and a draft of consultation notes they \
can edit and accept.

Hard rules:
- Use ONLY the data supplied. Never invent symptoms, findings, history, or results.
- Do not diagnose and do not prescribe. If the data suggests a pattern worth the \
doctor's attention, state the pattern, not a conclusion.
- If a field is missing or empty, do not speculate about it. Note it under \
missingInformation if it materially matters.
- Draft notes must read as a doctor's own notes: factual, terse, clinical. No \
preamble, no "the patient presents with" padding, no emoji.
- Keep the summary to 3-4 sentences."""

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "3-4 sentences covering the presentation and anything notable "
                           "in the history.",
        },
        "keyFindings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Bullet points a doctor should not miss, including abnormal "
                           "vitals and relevant prior history.",
        },
        "recommendedNotes": {
            "type": "string",
            "description": "Draft consultation notes, ready for the doctor to edit.",
        },
        "missingInformation": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Data absent from the record that would materially change "
                           "assessment. Empty array if nothing significant is missing.",
        },
    },
    "required": ["summary", "keyFindings", "recommendedNotes", "missingInformation"],
}


# ── Transport ────────────────────────────────────────────────────────────────

def _unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason, "model": None}


def _call_gemini(system_prompt: str, parts: List[dict], schema: dict) -> dict:
    """
    One Gemini generateContent call with a JSON response schema.
    Returns {'available': True, 'data': {...}, 'model': ...} or an unavailable dict.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _unavailable("GEMINI_API_KEY is not set")

    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "temperature": 0.2,   # clinical text: prefer consistency over variety
        },
    }

    try:
        response = requests.post(
            f"{API_BASE}/{MODEL}:generateContent",
            params={"key": api_key},
            json=body,
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return _unavailable(f"Gemini returned HTTP {response.status_code}")

        payload = response.json()
        candidates = payload.get("candidates") or []
        if not candidates:
            # Safety filters return 200 with no candidates and a promptFeedback block.
            blocked = payload.get("promptFeedback", {}).get("blockReason")
            return _unavailable(f"blocked by content filter ({blocked})" if blocked
                                else "Gemini returned no candidates")

        text = "".join(
            part.get("text", "")
            for part in candidates[0].get("content", {}).get("parts", [])
        )
        if not text.strip():
            return _unavailable("Gemini returned an empty response")

        return {"available": True, "data": json.loads(text), "model": MODEL}

    except requests.Timeout:
        return _unavailable("Gemini request timed out")
    except requests.RequestException as exc:
        return _unavailable(f"network error contacting Gemini: {type(exc).__name__}")
    except (ValueError, KeyError, IndexError):
        return _unavailable("Gemini response could not be parsed")


def _split_data_url(data_url: str):
    """'data:image/png;base64,AAAA' -> ('image/png', 'AAAA'). Returns (None, None) if not one."""
    match = re.match(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", data_url or "", re.DOTALL)
    if not match:
        return None, None
    return match.group(1), match.group(2)


# ── Public API ───────────────────────────────────────────────────────────────

def analyse_clinical_image(image_data_url: str, context: dict) -> dict:
    """
    context: {age, gender, symptoms[], allergies[], reasonForVisit, notes}
    Returns {available, model, imageQuality, observations, possibleConditions,
             recommendedNextSteps, reason}
    """
    mime_type, b64 = _split_data_url(image_data_url)
    if not b64:
        return {**_unavailable("image is not a base64 data URL"),
                "imageQuality": "", "observations": [],
                "possibleConditions": [], "recommendedNextSteps": []}

    # Guard the request size before spending a round trip on it.
    try:
        size_mb = len(base64.b64decode(b64, validate=False)) / (1024 * 1024)
    except Exception:
        return {**_unavailable("image data could not be decoded"),
                "imageQuality": "", "observations": [],
                "possibleConditions": [], "recommendedNextSteps": []}
    if size_mb > 18:
        return {**_unavailable(f"image is too large to analyse ({size_mb:.1f}MB)"),
                "imageQuality": "", "observations": [],
                "possibleConditions": [], "recommendedNextSteps": []}

    clinical_context = {
        "age": context.get("age"),
        "gender": context.get("gender"),
        "reasonForVisit": context.get("reasonForVisit"),
        "recordedSymptoms": context.get("symptoms", []),
        "knownAllergies": context.get("allergies", []),
        "doctorNotes": context.get("notes"),
    }

    result = _call_gemini(
        IMAGE_SYSTEM_PROMPT,
        [
            {"inline_data": {"mime_type": mime_type, "data": b64}},
            {"text": "Analyse this clinical image. Patient context:\n"
                     + json.dumps(clinical_context, indent=2)},
        ],
        IMAGE_SCHEMA,
    )

    if not result["available"]:
        return {**result, "imageQuality": "", "observations": [],
                "possibleConditions": [], "recommendedNextSteps": []}

    data = result["data"]
    return {
        "available": True,
        "model": result["model"],
        "reason": None,
        "imageQuality": data.get("imageQuality", ""),
        "observations": data.get("observations", []),
        "possibleConditions": data.get("possibleConditions", []),
        "recommendedNextSteps": data.get("recommendedNextSteps", []),
    }


def generate_clinical_summary(patient_context: dict) -> dict:
    """
    patient_context carries this visit plus prior consultations and prescriptions.
    Returns {available, model, summary, keyFindings, recommendedNotes,
             missingInformation, reason}
    """
    result = _call_gemini(
        SUMMARY_SYSTEM_PROMPT,
        [{"text": "Summarise this consultation for the treating doctor.\n\n"
                  + json.dumps(patient_context, indent=2, default=str)}],
        SUMMARY_SCHEMA,
    )

    if not result["available"]:
        return {**result, "summary": "", "keyFindings": [],
                "recommendedNotes": "", "missingInformation": []}

    data = result["data"]
    return {
        "available": True,
        "model": result["model"],
        "reason": None,
        "summary": data.get("summary", ""),
        "keyFindings": data.get("keyFindings", []),
        "recommendedNotes": data.get("recommendedNotes", ""),
        "missingInformation": data.get("missingInformation", []),
    }
