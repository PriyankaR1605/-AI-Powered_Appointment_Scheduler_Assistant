from typing import Optional, Literal, Union
from pydantic import BaseModel, Field

# ==============================================================================
# Request Models
# ==============================================================================

class TextAppointmentRequest(BaseModel):
    """Input payload for text-based appointment scheduling."""
    text: str = Field(
        ..., 
        description="Raw natural language text containing appointment details",
        json_schema_extra={"example": "Book dentist next Friday at 3pm"}
    )

# ==============================================================================
# Step 1: OCR / Text Extraction Models
# ==============================================================================

class OCRResponse(BaseModel):
    """Output schema for Step 1: Ingestion & OCR/Text extraction."""
    raw_text: str = Field(..., description="Extracted raw text from input or image")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")

# ==============================================================================
# Step 2: Entity Extraction Models
# ==============================================================================

class Entities(BaseModel):
    """Extracted raw phrases from the user request."""
    date_phrase: Optional[str] = Field(None, description="Extracted date expression, e.g., 'next Friday'")
    time_phrase: Optional[str] = Field(None, description="Extracted time expression, e.g., '3pm'")
    department: Optional[str] = Field(None, description="Extracted medical department, e.g., 'dentist'")

class ExtractionResponse(BaseModel):
    """Output schema for Step 2: Entity extraction via LLM."""
    entities: Entities
    entities_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")

# ==============================================================================
# Step 3: Normalization Models (Asia/Kolkata)
# ==============================================================================

class NormalizedAppointment(BaseModel):
    """Standardized ISO calendar and clock details."""
    date: Optional[str] = Field(None, description="ISO 8601 formatted date (YYYY-MM-DD)")
    time: Optional[str] = Field(None, description="24-hour formatted time (HH:MM)")
    tz: str = Field(default="Asia/Kolkata", description="Timezone name (strictly Asia/Kolkata)")

class NormalizationResponse(BaseModel):
    """Output schema for Step 3: Temporal and timezone normalization."""
    normalized: NormalizedAppointment
    normalization_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")

# ==============================================================================
# Step 4: Final Appointment Models & Guardrails
# ==============================================================================

class AppointmentDetails(BaseModel):
    """Standardized appointment details."""
    department: str = Field(..., description="Normalized medical department name (e.g., Dentistry)")
    date: str = Field(..., description="Normalized ISO date (YYYY-MM-DD)")
    time: str = Field(..., description="Normalized 24h time (HH:MM)")
    tz: str = Field(default="Asia/Kolkata", description="Target timezone")

class AppointmentResponse(BaseModel):
    """
    Final Output conforming to Problem Statement Step 4 & Guardrails.
    - If valid: returns appointment details with status='ok'
    - If ambiguous/invalid: returns status='needs_clarification' with descriptive message
    """
    appointment: Optional[AppointmentDetails] = None
    status: Literal["ok", "needs_clarification"]
    message: Optional[str] = None

# ==============================================================================
# Complete Pipeline Response (Combined Step-by-Step Transparency)
# ==============================================================================

class PipelineResponse(BaseModel):
    """Full transparency object returning outputs from all 4 pipeline stages."""
    step1_ocr: OCRResponse
    step2_extraction: ExtractionResponse
    step3_normalization: NormalizationResponse
    step4_appointment: AppointmentResponse
