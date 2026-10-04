"""
Step 2: Entity Extraction Service.
Uses Google Gemini AI to extract temporal phrases (date, time) and medical department
from raw natural language or OCR-extracted text.
"""

import os
import json
import re
import logging
from typing import Optional
from app.models.schemas import ExtractionResponse, Entities
from app.config import settings
from app.utils.department_map import CANONICAL_DEPARTMENTS

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

EXTRACTION_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
]

EXTRACTION_SYSTEM_PROMPT = """
You are a precise medical appointment extraction assistant.
Given a raw user request or OCR text, extract the appointment entities accurately.

Target Entities:
1. "date_phrase": Natural language date expression (e.g., "next Friday", "tomorrow", "October 15th", "2026-10-25", or null if not mentioned).
2. "time_phrase": Natural language time expression (e.g., "3pm", "15:00", "morning at 10", "10:30 AM", or null if not mentioned).
3. "department": Medical department or practitioner specialty (e.g., "dentist", "cardiology", "dermatologist", "orthopedics", "general physician", or null if not mentioned).

Confidence:
Assign "entities_confidence" as a float between 0.0 and 1.0 based on how clear and unambiguous the entities are in the text.
If any key entity (department, date, or time) is missing or vague, lower the confidence accordingly.

Output Format:
You MUST respond ONLY with a valid JSON object matching this schema without any markdown formatting or commentary:
{
  "entities": {
    "date_phrase": "string or null",
    "time_phrase": "string or null",
    "department": "string or null"
  },
  "entities_confidence": 0.90
}
"""


def _clean_ocr_text(text: str) -> str:
    """Normalize common OCR artifacts, slang, and abbreviations."""
    t = text.lower().strip()
    # Normalize common abbreviations
    t = re.sub(r"\bnxt\b", "next", t)
    t = re.sub(r"\btmrw\b|\btmr\b|\btom\b", "tomorrow", t)
    t = re.sub(r"\bmon\b(?!\w)", "monday", t)
    t = re.sub(r"\btue\b|\btues\b", "tuesday", t)
    t = re.sub(r"\bwed\b|\bweds\b", "wednesday", t)
    t = re.sub(r"\bthu\b|\bthur\b|\bthurs\b", "thursday", t)
    t = re.sub(r"\bfri\b(?!\w)", "friday", t)
    t = re.sub(r"\bsat\b(?!\w)", "saturday", t)
    t = re.sub(r"\bsun\b(?!\w)", "sunday", t)
    t = re.sub(r"\bapt\b|\bappmnt\b|\bapp\b", "appointment", t)
    t = re.sub(r"\s*@\s*", " at ", t)
    return t


def _heuristic_entity_extraction(raw_text: str) -> ExtractionResponse:
    """
    Fast rule-based entity extraction fallback (used for offline testing or when API key is unavailable/rate-limited).
    """
    cleaned = _clean_ocr_text(raw_text)
    
    # 1. Department matching against CANONICAL_DEPARTMENTS dictionary and extra terms
    detected_dept = None
    all_dept_keys = sorted(list(CANONICAL_DEPARTMENTS.keys()) + [
        "urology", "urologist", "gynecology", "gynecologist", "oncology", "oncologist",
        "physiotherapy", "physiotherapist", "radiology", "radiologist", "surgery", "surgeon",
        "pulmonology", "pulmonologist", "gastroenterology", "gastroenterologist",
        "neurology", "neurologist", "cardiology", "cardiologist", "dentistry", "dentist",
        "dermatology", "dermatologist", "ophthalmology", "ophthalmologist", "pediatrics", "pediatrician"
    ], key=lambda x: len(x), reverse=True)

    for d in all_dept_keys:
        if re.search(rf"\b{re.escape(d)}\b", cleaned):
            detected_dept = d
            break

    # 2. Time phrase matching
    time_patterns = [
        r"\b(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b",
        r"\b(?:at\s+)?(\d{1,2}\s*(?:am|pm))\b",
        r"\b(?:at\s+)?(\d{1,2}:\d{2})\b",
        r"\b(?:in\s+the\s+)?(?:morning|afternoon|evening|noon|night)\s*(?:at\s+\d{1,2}(?::\d{2})?)?\b",
        r"\b(?:at\s+)?(\d{1,2})\s*o['\s]?clock\b",
    ]
    detected_time = None
    for tp in time_patterns:
        match = re.search(tp, cleaned)
        if match:
            detected_time = match.group(0).replace("at ", "").strip()
            break

    # 3. Date phrase matching
    date_patterns = [
        r"\b(?:next|this|coming|on)?\s*(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\b(?:day after tomorrow|tomorrow|today)\b",
        r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",
        r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*(?:\s+\d{2,4})?\b",
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{2,4})?\b",
    ]
    detected_date = None
    for dp in date_patterns:
        match = re.search(dp, cleaned)
        if match:
            detected_date = match.group(0).strip()
            break

    # Calculate confidence based on extracted entities
    found_count = sum(1 for item in [detected_dept, detected_date, detected_time] if item)
    if found_count == 3:
        confidence = 0.90
    elif found_count == 2:
        confidence = 0.65
    elif found_count == 1:
        confidence = 0.35
    else:
        confidence = 0.0

    return ExtractionResponse(
        entities=Entities(
            date_phrase=detected_date,
            time_phrase=detected_time,
            department=detected_dept
        ),
        entities_confidence=confidence
    )


def extract_entities(raw_text: str) -> ExtractionResponse:
    """
    Step 2: Extract entities from raw text using Google Gemini with multi-model fallback and heuristic backup.
    """
    cleaned_text = raw_text.strip()
    if not cleaned_text:
        return ExtractionResponse(
            entities=Entities(date_phrase=None, time_phrase=None, department=None),
            entities_confidence=0.0
        )

    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key or not GENAI_AVAILABLE:
        logger.info("Using heuristic entity extraction fallback (GEMINI_API_KEY not configured).")
        return _heuristic_entity_extraction(cleaned_text)

    try:
        genai.configure(api_key=api_key)
        for model_name in EXTRACTION_MODELS:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=EXTRACTION_SYSTEM_PROMPT,
                    generation_config={"response_mime_type": "application/json"}
                )
                prompt = f"User Request: {cleaned_text}"
                response = model.generate_content(prompt, request_options={"timeout": 8})
                raw_response_text = response.text.strip()
                
                # Clean potential markdown fences
                cleaned_json = re.sub(r"^```(?:json)?\s*", "", raw_response_text)
                cleaned_json = re.sub(r"```$", "", cleaned_json).strip()
                
                data = json.loads(cleaned_json)
                entities_data = data.get("entities", {})
                
                return ExtractionResponse(
                    entities=Entities(
                        date_phrase=entities_data.get("date_phrase"),
                        time_phrase=entities_data.get("time_phrase"),
                        department=entities_data.get("department")
                    ),
                    entities_confidence=float(data.get("entities_confidence", 0.90))
                )
            except Exception as model_err:
                logger.warning(f"Model {model_name} failed for entity extraction: {model_err}")
                continue
    except Exception as e:
        logger.error(f"Gemini entity extraction failed: {e}. Falling back to heuristic extractor.")

    return _heuristic_entity_extraction(cleaned_text)

