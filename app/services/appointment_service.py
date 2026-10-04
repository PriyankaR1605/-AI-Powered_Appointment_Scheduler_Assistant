"""
Step 4: Final Appointment Consolidation Service.
Combines entities, normalized values, applies department canonical normalization,
and enforces guardrails.
"""

from typing import Optional
from app.models.schemas import (
    ExtractionResponse,
    NormalizationResponse,
    AppointmentResponse,
    AppointmentDetails,
)
from app.utils.guardrails import evaluate_guardrails
from app.utils.department_map import normalize_department_name


def consolidate_appointment(
    extraction: ExtractionResponse,
    normalization: NormalizationResponse
) -> AppointmentResponse:
    """
    Step 4: Assemble final appointment JSON.
    
    Expected Output (JSON) on success:
    {
      "appointment": {
        "department": "Dentistry",
        "date": "2025-09-26",
        "time": "15:00",
        "tz": "Asia/Kolkata"
      },
      "status": "ok"
    }
    
    Guardrail / Exit Condition (JSON) on failure:
    {
      "status": "needs_clarification",
      "message": "Ambiguous date/time or department"
    }
    """
    # 1. Run guardrail checks
    is_valid, guardrail_message = evaluate_guardrails(extraction, normalization)
    
    if not is_valid:
        return AppointmentResponse(
            appointment=None,
            status="needs_clarification",
            message=guardrail_message
        )
        
    # 2. Canonical department name mapping
    canonical_dept = normalize_department_name(extraction.entities.department)
    if not canonical_dept:
        canonical_dept = extraction.entities.department
        
    # 3. Build confirmed appointment object
    details = AppointmentDetails(
        department=canonical_dept,
        date=normalization.normalized.date,
        time=normalization.normalized.time,
        tz=normalization.normalized.tz or "Asia/Kolkata"
    )
    
    return AppointmentResponse(
        appointment=details,
        status="ok",
        message=None
    )
