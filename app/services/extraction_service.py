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

logger = logging.getLogger(__name__)

# Try to import Google Gemini library
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

EXTRACTION_SYSTEM_PROMPT = """
You are a precise medical appointment extraction assistant.
Given a raw user request or OCR text, extract the appointment entities accurately.

Target Entities:
1. "date_phrase": Natural language date expression (e.g., "next Friday", "tomorrow", "October 15th", or null if not mentioned).
2. "time_phrase": Natural language time expression (e.g., "3pm", "15:00", "morning at 10", or null if not mentioned).
3. "department": Medical department or practitioner specialty (e.g., "dentist", "cardiology", "dermatologist", or null if not mentioned).

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
  "entities_confidence": 0.85
}
"""


def _heuristic_entity_extraction(raw_text: str) -> ExtractionResponse:
    """
    Fast rule-based entity extraction fallback (useful for offline testing or when API key is not configured).
    """
    text_lower = raw_text.lower().strip()
    
    # 1. Department matching
    departments = [
        "dentist", "dental", "teeth", "cardiologist", "cardiology", "heart",
        "dermatologist", "dermatology", "skin", "ophthalmologist", "ophthalmology", "eye",
        "neurologist", "neurology", "neuro", "orthopedic", "orthopedics", "bone",
        "pediatrician", "pediatrics", "general physician", "doctor", "gp", "ent"
    ]
    detected_dept = None
    for d in departments:
        if re.search(rf"\b{re.escape(d)}\b", text_lower):
            detected_dept = d
            break

    # 2. Time phrase matching (regex)
    time_pattern = r"(\b(?:at\s+|@\s*)?\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\b\d{1,2}:\d{2}\b)"
    time_match = re.search(time_pattern, text_lower)
    if time_match:
        detected_time = time_match.group(1).replace("at ", "").replace("@", "").strip()
    else:
        detected_time = None

    # 3. Date phrase matching
    date_patterns = [
        r"\b(?:next|this|coming|on)?\s*(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\b(?:tomorrow|today|day after tomorrow)\b",
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*(?:\s+\d{4})?\b",
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    ]
    detected_date = None
    for pattern in date_patterns:
        match = re.search(pattern, text_lower)
        if match:
            detected_date = match.group(0).strip()
            break

    # Calculate confidence based on extracted entities
    found_count = sum(1 for item in [detected_dept, detected_date, detected_time] if item)
    confidence = 0.90 if found_count == 3 else (0.50 if found_count == 2 else 0.20)

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
    Step 2: Extract entities from raw text using Gemini 1.5 Flash (or heuristic fallback).
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
        # Use gemini-3.8-flash (or gemini-flash-latest) for fast structured outputs
        model = genai.GenerativeModel(
            model_name="gemini-3.8-flash",
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            generation_config={"response_mime_type": "application/json"}
        )
        
        prompt = f"User Request: {cleaned_text}"
        response = model.generate_content(prompt)
        raw_response_text = response.text.strip()
        
        # Clean potential markdown fences
        cleaned_json = re.sub(r"^```json\s*", "", raw_response_text)
        cleaned_json = re.sub(r"```$", "", cleaned_json).strip()
        
        data = json.loads(cleaned_json)
        entities_data = data.get("entities", {})
        
        return ExtractionResponse(
            entities=Entities(
                date_phrase=entities_data.get("date_phrase"),
                time_phrase=entities_data.get("time_phrase"),
                department=entities_data.get("department")
            ),
            entities_confidence=float(data.get("entities_confidence", 0.85))
        )
    except Exception as e:
        logger.error(f"Gemini entity extraction failed: {e}. Falling back to heuristic extractor.")
        return _heuristic_entity_extraction(cleaned_text)
