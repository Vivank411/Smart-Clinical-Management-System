"""
AI Clinical Analysis Engine.

Second layer of a two-layer safety design:

  Layer 1 (clinical_safety.py)  Deterministic rules over the local reference
                                tables. Always available, instant, auditable.
                                This is the floor — it cannot regress.

  Layer 2 (this module)         Claude analyses the whole prescription for
                                conflicts the reference tables don't cover.
                                Broad, but non-deterministic and network-bound.

Findings are merged and labelled by source so the prescriber can tell a
database-verified conflict from an AI-identified one. When this layer is
unavailable the caller still gets every layer-1 finding, plus a flag so the UI
can say plainly that AI checking didn't run.
"""

import json
import os
from typing import List, Optional

MODEL = "claude-opus-5"
MAX_TOKENS = 4000
TIMEOUT_SECONDS = 25.0

SYSTEM_PROMPT = """You are a clinical safety analyst inside an e-prescribing system, \
writing for the prescribing physician.

You receive a patient, a prescription under construction, and the conflicts a \
deterministic rule engine has already found against a limited local drug database.

You have two jobs.

1. ADDITIONAL CONFLICTS. The local database covers only a small set of drug classes \
and interaction pairs, so it misses a great deal. Analyse the whole prescription and \
report clinically significant conflicts it did NOT find, across four categories: \
allergy (including cross-reactivity), drug-drug interaction, therapeutic duplication, \
and dosage outside the accepted range for this patient's age.
   - Do NOT repeat anything already in alreadyDetected. Those are handled.
   - Report only conflicts you are confident are clinically significant. A false alarm \
costs real attention and trains physicians to dismiss alerts; do not pad the list.
   - Severity is High (may cause serious harm), Moderate (needs consideration), or \
Low (worth noting).

2. EXPLANATION. Write 2-3 plain sentences explaining what matters most across ALL \
conflicts — the rule-detected ones and any you added.

Hard rules:
- Never dispute or soften a rule-detected conflict. Those are established fact.
- Never diagnose, and never state what the physician should decide.
- When an alternatives list is supplied, choose ONLY from it. If it is empty, return an \
empty array rather than naming a medicine outside the formulary.
- Base every finding on the medicines and allergies given. Do not invent patient \
history, test results, or comorbidities.
- Write for a doctor: precise, no hedging, no padding, no emoji.
- If you find no additional conflicts, return an empty array. That is a valid and \
common answer."""

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "additionalConflicts": {
            "type": "array",
            "description": "Clinically significant conflicts the rule engine missed. "
                           "Empty array if none.",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string",
                             "enum": ["allergy", "interaction", "duplicate", "dosage"]},
                    "severity": {"type": "string", "enum": ["High", "Moderate", "Low"]},
                    "title": {"type": "string",
                              "description": "Short headline, e.g. 'Drug Interaction Detected'."},
                    "detail": {"type": "string",
                               "description": "One or two sentences on the clinical risk."},
                    "medicine": {"type": "string",
                                 "description": "The medicine this conflict is about."},
                    "relatedTo": {"type": "string",
                                  "description": "The other medicine or the allergen involved. "
                                                 "Empty string if not applicable."},
                },
                "required": ["type", "severity", "title", "detail", "medicine", "relatedTo"],
                "additionalProperties": False,
            },
        },
        "explanation": {
            "type": "string",
            "description": "2-3 sentences covering the most important risk across all conflicts.",
        },
        "suggestion": {
            "type": "string",
            "description": "One sentence naming alternatives from the supplied list, or an "
                           "empty string if the list is empty.",
        },
        "alternatives": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Medicine names chosen from the supplied candidate list only.",
        },
    },
    "required": ["additionalConflicts", "explanation", "suggestion", "alternatives"],
    "additionalProperties": False,
}


def _local_explanation(conflicts: List[dict], candidates: List[dict]) -> dict:
    """Deterministic text assembled from the rule findings, used when Claude is unreachable."""
    if not conflicts:
        return {"additionalConflicts": [], "explanation": "", "suggestion": "",
                "alternatives": [], "model": None, "available": False}

    primary = conflicts[0]
    parts = [primary.get("detail", "A prescribing conflict was detected.")]
    if primary.get("type") == "allergy":
        parts.append(
            f"The patient has a recorded {primary.get('allergen', 'drug')} allergy and "
            f"{primary.get('medicine', 'this medicine')} belongs to the "
            f"{primary.get('drugClass', 'same')} class."
        )
    names = [c["name"] for c in candidates[:3]]
    return {
        "additionalConflicts": [],
        "explanation": " ".join(p for p in parts if p),
        "suggestion": f"Alternatives in the same category: {', '.join(names)}." if names else "",
        "alternatives": names,
        "model": None,
        "available": False,
    }


def analyse_prescription(rule_conflicts: List[dict], patient: dict, medicine: dict,
                         current_medicines: List[dict], candidates: List[dict]) -> dict:
    """
    Second-pass analysis over the whole prescription.

    Returns {additionalConflicts, explanation, suggestion, alternatives, model, available}.
    `available` is False when the call could not be made or failed — the caller
    surfaces that to the prescriber rather than implying the prescription was
    fully checked.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _local_explanation(rule_conflicts, candidates)

    try:
        import anthropic
    except ImportError:
        return _local_explanation(rule_conflicts, candidates)

    payload = {
        "patient": {
            "age": patient.get("age"),
            "gender": patient.get("gender"),
            "recordedAllergies": patient.get("allergies", []),
        },
        "medicineBeingAdded": {
            "name": medicine.get("name"),
            "dosage": medicine.get("dosage"),
            "frequency": medicine.get("frequency"),
            "duration": medicine.get("duration"),
        },
        "otherMedicinesOnPrescription": current_medicines,
        "alreadyDetected": rule_conflicts,
        "alternativeCandidates": candidates,
    }

    try:
        client = anthropic.Anthropic(timeout=TIMEOUT_SECONDS, max_retries=1)
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={
                "effort": "high",   # detection accuracy matters more than latency here
                "format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA},
            },
            messages=[{
                "role": "user",
                "content": "Analyse this prescription for clinical safety conflicts.\n\n"
                           + json.dumps(payload, indent=2),
            }],
        )

        # Safety classifiers return HTTP 200 with empty content on a refusal, so
        # check stop_reason before indexing.
        if response.stop_reason == "refusal":
            return _local_explanation(rule_conflicts, candidates)

        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            return _local_explanation(rule_conflicts, candidates)

        data = json.loads(text)

        allowed = {c["name"] for c in candidates}
        # Enforce the formulary constraint in code — a prompt rule is not a guarantee.
        alternatives = [a for a in data.get("alternatives", []) if a in allowed]

        additional = []
        for c in data.get("additionalConflicts", []):
            additional.append({
                "type": c.get("type", "interaction"),
                "severity": c.get("severity", "Moderate"),
                "title": c.get("title", "Potential Conflict"),
                "detail": c.get("detail", ""),
                "medicine": c.get("medicine", ""),
                "relatedTo": c.get("relatedTo", ""),
                "source": "ai",
            })

        return {
            "additionalConflicts": additional,
            "explanation": data.get("explanation", ""),
            "suggestion": data.get("suggestion", "") if alternatives else "",
            "alternatives": alternatives,
            "model": MODEL,
            "available": True,
        }

    except Exception:
        # Auth, rate limit, timeout, malformed JSON — all degrade to the rule
        # findings alone, flagged as an incomplete check.
        return _local_explanation(rule_conflicts, candidates)
