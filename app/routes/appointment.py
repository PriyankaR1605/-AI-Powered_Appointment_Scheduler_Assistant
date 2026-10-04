from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import Optional
from app.models.schemas import (
    TextAppointmentRequest,
    OCRResponse,
    ExtractionResponse,
    NormalizationResponse,
    AppointmentResponse,
    PipelineResponse,
)
from app.services.ocr_service import extract_text_from_string, extract_text_from_image
from app.services.extraction_service import extract_entities
from app.services.normalization_service import normalize_datetime
from app.services.appointment_service import consolidate_appointment

router = APIRouter(prefix="/appointment", tags=["Appointment Scheduling"])


@router.post(
    "/schedule/text",
    response_model=PipelineResponse,
    summary="Schedule an appointment from typed text",
    description="Processes natural language text through the full 4-step pipeline: Text Passthrough ➔ Extraction ➔ Normalization ➔ Guardrails & Final Appointment."
)
def schedule_from_text(payload: TextAppointmentRequest):
    """
    Example Input:
    ```json
    {
      "text": "Book dentist next Friday at 3pm"
    }
    ```
    """
    # Step 1: Text extraction / passthrough
    step1 = extract_text_from_string(payload.text)
    
    # Step 2: Entity extraction (AI or fallback)
    step2 = extract_entities(step1.raw_text)
    
    # Step 3: Temporal normalization to Asia/Kolkata
    step3 = normalize_datetime(step2.entities.date_phrase, step2.entities.time_phrase)
    
    # Step 4: Final Appointment assembly with guardrails
    step4 = consolidate_appointment(step2, step3)
    
    return PipelineResponse(
        step1_ocr=step1,
        step2_extraction=step2,
        step3_normalization=step3,
        step4_appointment=step4
    )


try:
    from fastapi.dependencies.utils import ensure_multipart_is_installed
    ensure_multipart_is_installed()
    MULTIPART_AVAILABLE = True
except Exception:
    MULTIPART_AVAILABLE = False


if MULTIPART_AVAILABLE:
    @router.post(
        "/schedule/image",
        response_model=PipelineResponse,
        summary="Schedule an appointment from an uploaded image",
        description="Processes an image (scanned note, handwritten note, email screenshot) through OCR and the full 4-step pipeline."
    )
    async def schedule_from_image(file: UploadFile = File(...)):
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type '{file.content_type}'. Please upload an image file."
            )

        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

        try:
            step1 = extract_text_from_image(image_bytes)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"OCR error: {str(e)}")

        step2 = extract_entities(step1.raw_text)
        step3 = normalize_datetime(step2.entities.date_phrase, step2.entities.time_phrase)
        step4 = consolidate_appointment(step2, step3)

        return PipelineResponse(
            step1_ocr=step1,
            step2_extraction=step2,
            step3_normalization=step3,
            step4_appointment=step4
        )

    # Debug Step Routes
    debug_router = APIRouter(prefix="/debug", tags=["Debug Pipeline Steps"])

    @debug_router.post("/step1-ocr", response_model=OCRResponse, summary="Debug Step 1: OCR / Text extraction")
    async def debug_step1(
        file: Optional[UploadFile] = File(None),
        text: Optional[str] = Form(None)
    ):
        if file:
            return extract_text_from_image(await file.read())
        elif text:
            return extract_text_from_string(text)
        raise HTTPException(status_code=400, detail="Provide either 'file' (image) or 'text'.")

    @debug_router.post("/step2-extract", response_model=ExtractionResponse, summary="Debug Step 2: Entity Extraction")
    def debug_step2(raw_text: str = Form(...)):
        return extract_entities(raw_text)

    @debug_router.post("/step3-normalize", response_model=NormalizationResponse, summary="Debug Step 3: Normalization")
    def debug_step3(
        date_phrase: Optional[str] = Form(None),
        time_phrase: Optional[str] = Form(None)
    ):
        return normalize_datetime(date_phrase, time_phrase)
else:
    debug_router = APIRouter(prefix="/debug", tags=["Debug Pipeline Steps"])

    @router.post("/schedule/image", summary="Schedule an appointment from an image")
    async def schedule_from_image():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="python-multipart package is required for file uploads. Run 'pip install python-multipart'."
        )

