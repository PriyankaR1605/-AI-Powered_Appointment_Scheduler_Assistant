from fastapi.testclient import TestClient
from app.main import app
from app.services.ocr_service import extract_text_from_string
from app.services.extraction_service import _heuristic_entity_extraction
from app.services.normalization_service import _heuristic_normalization
from app.services.appointment_service import consolidate_appointment
from app.utils.department_map import normalize_department_name
from app.models.schemas import ExtractionResponse, Entities, NormalizationResponse, NormalizedAppointment

client = TestClient(app)

# ==============================================================================
# Step 1 Unit Tests
# ==============================================================================

def test_ocr_text_passthrough():
    result = extract_text_from_string("Book dentist next Friday at 3pm")
    assert result.raw_text == "Book dentist next Friday at 3pm"
    assert result.confidence == 0.99

def test_ocr_text_empty():
    result = extract_text_from_string("   ")
    assert result.raw_text == ""
    assert result.confidence == 0.0

# ==============================================================================
# Step 2 Unit Tests
# ==============================================================================

def test_heuristic_entity_extraction_happy_path():
    result = _heuristic_entity_extraction("Book dentist next Friday at 3pm")
    assert result.entities.department == "dentist"
    assert result.entities.date_phrase == "next friday"
    assert result.entities.time_phrase == "3pm"
    assert result.entities_confidence >= 0.80

def test_heuristic_entity_extraction_missing_fields():
    result = _heuristic_entity_extraction("I want an appointment")
    assert result.entities.department is None
    assert result.entities.date_phrase is None
    assert result.entities.time_phrase is None
    assert result.entities_confidence <= 0.60

# ==============================================================================
# Step 3 Unit Tests
# ==============================================================================

def test_heuristic_normalization():
    result = _heuristic_normalization("tomorrow", "3pm")
    assert result.normalized.time == "15:00"
    assert result.normalized.tz == "Asia/Kolkata"
    assert result.normalized.date is not None
    assert result.normalization_confidence >= 0.85

def test_department_normalization():
    assert normalize_department_name("dentist") == "Dentistry"
    assert normalize_department_name("heart") == "Cardiology"
    assert normalize_department_name("skin") == "Dermatology"
    assert normalize_department_name("unknown clinic") == "Unknown Clinic"

# ==============================================================================
# Step 4 & Guardrails Unit Tests
# ==============================================================================

def test_consolidation_success():
    ext = ExtractionResponse(
        entities=Entities(date_phrase="next Friday", time_phrase="3pm", department="dentist"),
        entities_confidence=0.85
    )
    norm = NormalizationResponse(
        normalized=NormalizedAppointment(date="2025-09-26", time="15:00", tz="Asia/Kolkata"),
        normalization_confidence=0.90
    )
    resp = consolidate_appointment(ext, norm)
    assert resp.status == "ok"
    assert resp.appointment is not None
    assert resp.appointment.department == "Dentistry"
    assert resp.appointment.date == "2025-09-26"
    assert resp.appointment.time == "15:00"
    assert resp.appointment.tz == "Asia/Kolkata"

def test_consolidation_guardrail_missing_department():
    ext = ExtractionResponse(
        entities=Entities(date_phrase="next Friday", time_phrase="3pm", department=None),
        entities_confidence=0.85
    )
    norm = NormalizationResponse(
        normalized=NormalizedAppointment(date="2025-09-26", time="15:00", tz="Asia/Kolkata"),
        normalization_confidence=0.90
    )
    resp = consolidate_appointment(ext, norm)
    assert resp.status == "needs_clarification"
    assert resp.appointment is None
    assert "Ambiguous" in resp.message

# ==============================================================================
# API Integration Tests
# ==============================================================================

def test_api_schedule_text_endpoint():
    payload = {"text": "Book dentist next Friday at 3pm"}
    response = client.post("/appointment/schedule/text", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert "step1_ocr" in data
    assert "step2_extraction" in data
    assert "step3_normalization" in data
    assert "step4_appointment" in data
    
    # Check Step 1
    assert data["step1_ocr"]["raw_text"] == "Book dentist next Friday at 3pm"
    
    # Check Step 4
    appointment = data["step4_appointment"]
    assert appointment["status"] in ["ok", "needs_clarification"]

def test_api_ambiguous_text_triggers_guardrail():
    payload = {"text": "Schedule an appointment"}
    response = client.post("/appointment/schedule/text", json=payload)
    assert response.status_code == 200
    data = response.json()
    appointment = data["step4_appointment"]
    assert appointment["status"] == "needs_clarification"
    assert "Ambiguous" in appointment["message"]
