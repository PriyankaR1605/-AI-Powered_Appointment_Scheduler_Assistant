"""
Step 3: Normalization Service.
Maps natural language date/time expressions into standardized ISO 8601 calendar
and clock values strictly localized to Asia/Kolkata (IST).
"""

import os
import json
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    import pytz
    def get_ist_now() -> datetime:
        return datetime.now(pytz.timezone("Asia/Kolkata"))
except ImportError:
    IST_OFFSET = timezone(timedelta(hours=5, minutes=30))
    def get_ist_now() -> datetime:
        return datetime.now(IST_OFFSET)

from app.models.schemas import NormalizationResponse, NormalizedAppointment
from app.config import settings

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

NORMALIZATION_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
]

NORMALIZATION_SYSTEM_PROMPT = """
You are a temporal normalization engine for an appointment booking system in India.
Timezone is strictly: Asia/Kolkata (IST, UTC+05:30).

You will receive:
- Current Reference DateTime in Asia/Kolkata
- date_phrase: Natural language date (or null)
- time_phrase: Natural language time (or null)

Your task:
1. Map "date_phrase" to ISO 8601 date: "YYYY-MM-DD".
   - "next Friday" means the upcoming Friday following the current reference date.
   - "tomorrow" means current reference date + 1 day.
   - "October 15th" means 2026-10-15 (or corresponding year).
   - If ambiguous or missing, output null.
2. Map "time_phrase" to 24-hour time: "HH:MM".
   - "3pm" or "3:00 pm" -> "15:00"
   - "10:30am" -> "10:30"
   - "morning" / "morning at 10" -> "10:00" (or "09:00" if no hour given)
   - "afternoon" -> "14:00"
   - "evening" -> "18:00"
   - If ambiguous or missing, output null.
3. Compute "normalization_confidence" as a float between 0.0 and 1.0.
   - If both date and time are clearly normalized, confidence should be ~0.90 - 1.0.
   - If either is ambiguous or missing, lower confidence below 0.60.

Output Format:
You MUST respond ONLY with valid JSON without markdown fences:
{
  "normalized": {
    "date": "YYYY-MM-DD or null",
    "time": "HH:MM or null",
    "tz": "Asia/Kolkata"
  },
  "normalization_confidence": 0.90
}
"""

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12
}


def _heuristic_normalization(date_phrase: Optional[str], time_phrase: Optional[str]) -> NormalizationResponse:
    """
    Algorithmic fallback for normalizing common date/time phrases in Asia/Kolkata.
    """
    now = get_ist_now()
    normalized_date = None
    normalized_time = None
    
    # 1. Normalize Date
    if date_phrase:
        dp = date_phrase.lower().strip()
        
        # Relative keywords
        if "today" in dp:
            normalized_date = now.strftime("%Y-%m-%d")
        elif "tomorrow" in dp and "day after" not in dp:
            normalized_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "day after tomorrow" in dp:
            normalized_date = (now + timedelta(days=2)).strftime("%Y-%m-%d")
        else:
            # Check for weekday (e.g. "friday", "next friday", "coming monday", etc.)
            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for idx, day_name in enumerate(weekdays):
                if day_name in dp:
                    current_weekday = now.weekday()
                    days_ahead = (idx - current_weekday) % 7
                    if days_ahead <= 0:  # strictly upcoming day
                        days_ahead += 7
                    normalized_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                    break
            
            # Check for ISO date format YYYY-MM-DD or YYYY/MM/DD
            if not normalized_date:
                iso_match = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", dp)
                if iso_match:
                    year, month, day = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
                    try:
                        normalized_date = datetime(year, month, day).strftime("%Y-%m-%d")
                    except ValueError:
                        pass

            # Check for DD/MM/YYYY or DD-MM-YYYY
            if not normalized_date:
                dmy_match = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b", dp)
                if dmy_match:
                    day, month = int(dmy_match.group(1)), int(dmy_match.group(2))
                    raw_year = int(dmy_match.group(3))
                    year = raw_year if raw_year > 100 else (2000 + raw_year)
                    try:
                        normalized_date = datetime(year, month, day).strftime("%Y-%m-%d")
                    except ValueError:
                        pass

            # Check for "15th Oct" or "15 October 2026"
            if not normalized_date:
                d_m_match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)(?:\s+(\d{4}))?\b", dp)
                if d_m_match:
                    day = int(d_m_match.group(1))
                    month_name = d_m_match.group(2)
                    year = int(d_m_match.group(3)) if d_m_match.group(3) else now.year
                    if month_name in MONTH_MAP:
                        month = MONTH_MAP[month_name]
                        try:
                            d_obj = datetime(year, month, day)
                            if d_obj.date() < now.date() and not d_m_match.group(3):
                                d_obj = datetime(year + 1, month, day)
                            normalized_date = d_obj.strftime("%Y-%m-%d")
                        except ValueError:
                            pass

            # Check for "Oct 15th" or "October 15, 2026"
            if not normalized_date:
                m_d_match = re.search(r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?\b", dp)
                if m_d_match:
                    month_name = m_d_match.group(1)
                    day = int(m_d_match.group(2))
                    year = int(m_d_match.group(3)) if m_d_match.group(3) else now.year
                    if month_name in MONTH_MAP:
                        month = MONTH_MAP[month_name]
                        try:
                            d_obj = datetime(year, month, day)
                            if d_obj.date() < now.date() and not m_d_match.group(3):
                                d_obj = datetime(year + 1, month, day)
                            normalized_date = d_obj.strftime("%Y-%m-%d")
                        except ValueError:
                            pass

    # 2. Normalize Time
    if time_phrase:
        tp = time_phrase.lower().strip().replace("at ", "").replace("@", "").strip()
        match_12h = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", tp)
        match_24h = re.search(r"\b(\d{1,2}):(\d{2})\b", tp)
        match_period = re.search(r"\b(morning|afternoon|evening|night|noon)\b", tp)
        
        if match_12h:
            hour = int(match_12h.group(1))
            minute = int(match_12h.group(2) or 0)
            period = match_12h.group(3).lower()
            if period == "pm" and hour < 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                normalized_time = f"{hour:02d}:{minute:02d}"
        elif match_24h:
            hour = int(match_24h.group(1))
            minute = int(match_24h.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                normalized_time = f"{hour:02d}:{minute:02d}"
        elif match_period:
            period_val = match_period.group(1)
            time_defaults = {
                "morning": "09:00",
                "noon": "12:00",
                "afternoon": "14:00",
                "evening": "18:00",
                "night": "20:00"
            }
            normalized_time = time_defaults.get(period_val, "10:00")

    # Calculate confidence
    if normalized_date and normalized_time:
        confidence = 0.90
    elif normalized_date or normalized_time:
        confidence = 0.50
    else:
        confidence = 0.0

    return NormalizationResponse(
        normalized=NormalizedAppointment(
            date=normalized_date,
            time=normalized_time,
            tz=settings.DEFAULT_TIMEZONE
        ),
        normalization_confidence=confidence
    )


def normalize_datetime(
    date_phrase: Optional[str],
    time_phrase: Optional[str]
) -> NormalizationResponse:
    """
    Step 3: Normalize natural language date/time expressions to ISO 8601 in Asia/Kolkata.
    Uses Google Gemini with multi-model fallback and algorithmic heuristic backup.
    """
    if not date_phrase and not time_phrase:
        return NormalizationResponse(
            normalized=NormalizedAppointment(date=None, time=None, tz=settings.DEFAULT_TIMEZONE),
            normalization_confidence=0.0
        )

    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key or not GENAI_AVAILABLE:
        logger.info("Using heuristic normalization fallback (GEMINI_API_KEY not configured).")
        return _heuristic_normalization(date_phrase, time_phrase)

    current_time_str = get_ist_now().strftime("%Y-%m-%d %H:%M:%S (%A)")

    try:
        genai.configure(api_key=api_key)
        for model_name in NORMALIZATION_MODELS:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=NORMALIZATION_SYSTEM_PROMPT,
                    generation_config={"response_mime_type": "application/json"}
                )

                user_input_prompt = f"""
Current Reference DateTime: {current_time_str}
Input date_phrase: {json.dumps(date_phrase)}
Input time_phrase: {json.dumps(time_phrase)}
"""
                response = model.generate_content(user_input_prompt, request_options={"timeout": 8})
                raw_text = response.text.strip()
                
                cleaned_json = re.sub(r"^```(?:json)?\s*", "", raw_text)
                cleaned_json = re.sub(r"```$", "", cleaned_json).strip()
                
                data = json.loads(cleaned_json)
                norm_data = data.get("normalized", {})

                return NormalizationResponse(
                    normalized=NormalizedAppointment(
                        date=norm_data.get("date"),
                        time=norm_data.get("time"),
                        tz=settings.DEFAULT_TIMEZONE
                    ),
                    normalization_confidence=float(data.get("normalization_confidence", 0.90))
                )
            except Exception as model_err:
                logger.warning(f"Model {model_name} failed for normalization: {model_err}")
                continue
    except Exception as e:
        logger.error(f"Gemini normalization failed: {e}. Falling back to heuristic normalization.")

    return _heuristic_normalization(date_phrase, time_phrase)

