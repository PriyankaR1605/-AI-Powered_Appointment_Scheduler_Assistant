"""
Guardrail and validation checks to intercept ambiguous, incomplete,
or low-confidence appointment requests before final confirmation.
"""

from typing import Tuple
from app.models.schemas import ExtractionResponse, NormalizationResponse
from app.config import settings

def evaluate_guardrails(
    extraction: ExtractionResponse,
    normalization: NormalizationResponse
) -> Tuple[bool, str]:
    """
    Evaluates pipeline confidence and completeness against guardrails.
    
    Returns:
        (is_valid, message):
            - If valid: (True, "ok")
            - If invalid / ambiguous: (False, "Ambiguous date/time or department")
    """
    entities = extraction.entities
    normalized = normalization.normalized
    
    # 1. Check mandatory entities presence
    if not entities.department or not entities.department.strip():
        return False, "Ambiguous date/time or department"
        
    if not entities.date_phrase or not entities.date_phrase.strip():
        return False, "Ambiguous date/time or department"
        
    if not entities.time_phrase or not entities.time_phrase.strip():
        return False, "Ambiguous date/time or department"

    # 2. Check normalization resolution
    if not normalized.date or not normalized.time:
        return False, "Ambiguous date/time or department"

    # 3. Check confidence thresholds
    threshold = settings.CONFIDENCE_THRESHOLD
    if extraction.entities_confidence < threshold:
        return False, "Ambiguous date/time or department"
        
    if normalization.normalization_confidence < threshold:
        return False, "Ambiguous date/time or department"

    return True, "ok"
