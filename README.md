
# 🗓️ AI-Powered Appointment Scheduler Assistant

A resilient, production-ready backend service that parses natural language and document/image-based appointment requests into structured scheduling data following strict JSON schemas.

Designed for **Problem Statement 1: AI-Powered Appointment Scheduler Assistant** (Plum Benefits).

---

## 🏗️ Architecture & 4-Step Pipeline

```
                     [ User Input ]
                (Typed Text or Image Upload)
                             │
                             ▼
   ┌─────────────────────────────────────────────────────┐
   │ STEP 1: Ingestion & OCR / Text Extraction           │
   │  • Text: Sanitized passthrough (Confidence: ~0.99)  │
   │  • Image: PIL Preprocessing ➔ Tesseract OCR Engine  │
   └─────────────────────────┬───────────────────────────┘
                             │ Output: raw_text, confidence
                             ▼
   ┌─────────────────────────────────────────────────────┐
   │ STEP 2: Entity Extraction (Google Gemini 1.5 Flash) │
   │  • Extracts: date_phrase, time_phrase, department   │
   │  • Assigns: entities_confidence                     │
   └─────────────────────────┬───────────────────────────┘
                             │ Output: entities, entities_confidence
                             ▼
   ┌─────────────────────────────────────────────────────┐
   │ STEP 3: Normalization Engine (Asia/Kolkata)         │
   │  • Dynamic Reference Time: Passes current IST time  │
   │  • Maps natural phrases ➔ ISO 8601 Date & 24h Time │
   │  • Assigns: normalization_confidence                │
   └─────────────────────────┬───────────────────────────┘
                             │
                             ▼
   ┌─────────────────────────────────────────────────────┐
   │ GUARDRAIL VALIDATION LAYER                          │
   │  • Missing mandatory fields?                        │
   │  • Low confidence (< 0.60)?                         │
   │  • Ambiguous expressions?                           │
   │        │                               │            │
   │    [FAILED]                         [PASSED]        │
   │        │                               │            │
   │        ▼                               ▼            │
   │ 4a: EXIT CONDITION           4b: STEP 4 APPOINTMENT │
   │ {                            {                      │
   │   "status":                    "appointment": {     │
   │     "needs_clarification",       "department": ..., │
   │   "message": "..."               "date": ...,       │
   │ }                                "time": ...,       │
   │                                  "tz": ...          │
   │                                },                   │
   │                                "status": "ok"       │
   │                              }                      │
   └─────────────────────────────────────────────────────┘
```

---

## ⚡ Tech Stack

| Layer | Tool | Rationale |
|---|---|---|
| **Web Framework** | FastAPI | High throughput async endpoints + interactive Swagger UI (`/docs`) |
| **Validation** | Pydantic v2 | Strict JSON schema contract enforcement |
| **OCR Engine** | Tesseract + Pillow | Image preprocessing (contrast, grayscale, sharpening) + OCR text extraction |
| **LLM Reasoning** | Google Gemini 1.5 Flash | Robust natural language extraction & structured JSON generation |
| **Timezone** | Asia/Kolkata (IST) | Standardized UTC+05:30 calendar anchoring |
| **Testing** | Pytest / TestClient | Unit and integration test coverage across all pipeline stages |

---

## 📋 Prerequisites & Installation

### 1. Prerequisites
- Python 3.10+
- (Optional for Image OCR) **Tesseract OCR**:
  - **Windows**: Download installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and install to `C:\Program Files\Tesseract-OCR\`.
  - **Linux / Ubuntu**: `sudo apt install tesseract-ocr`
  - **macOS**: `brew install tesseract`

### 2. Clone & Setup Environment
```bash
# Clone the repository
git clone https://github.com/your-username/Plum_Benifites_Assignment.git
cd Plum_Benifites_Assignment

# Create virtual environment
python -m venv venv
# Activate on Windows:
venv\Scripts\activate
# Activate on Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure `.env`
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` and fill in:
```env
GEMINI_API_KEY=your_gemini_api_key_here
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
DEFAULT_TIMEZONE=Asia/Kolkata
```
*(Note: If `GEMINI_API_KEY` is not provided, the service automatically engages an algorithmic fallback so baseline testing and offline grading remain fully functional!)*

---

## 🚀 Running the Server

Start the FastAPI application:
```bash
uvicorn app.main:app --reload --port 8000
```
- Interactive API Docs (Swagger UI): `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

---

## 📡 API Endpoints & Usage

### 1. Full Pipeline (Text Input)
**Endpoint:** `POST /appointment/schedule/text`

#### Sample Request:
```bash
curl -X POST "http://localhost:8000/appointment/schedule/text" \
  -H "Content-Type: application/json" \
  -d '{"text": "Book dentist next Friday at 3pm"}'
```

#### Expected Response:
```json
{
  "step1_ocr": {
    "raw_text": "Book dentist next Friday at 3pm",
    "confidence": 0.99
  },
  "step2_extraction": {
    "entities": {
      "date_phrase": "next Friday",
      "time_phrase": "3pm",
      "department": "dentist"
    },
    "entities_confidence": 0.85
  },
  "step3_normalization": {
    "normalized": {
      "date": "2026-10-09",
      "time": "15:00",
      "tz": "Asia/Kolkata"
    },
    "normalization_confidence": 0.9
  },
  "step4_appointment": {
    "appointment": {
      "department": "Dentistry",
      "date": "2026-10-09",
      "time": "15:00",
      "tz": "Asia/Kolkata"
    },
    "status": "ok",
    "message": null
  }
}
```

---

### 2. Full Pipeline (Image OCR Input)
**Endpoint:** `POST /appointment/schedule/image`

#### Sample Request:
```bash
curl -X POST "http://localhost:8000/appointment/schedule/image" \
  -F "file=@sample_data/appointment_note.png"
```

---

### 3. Guardrail / Exit Condition (Ambiguous Request)
**Endpoint:** `POST /appointment/schedule/text`

#### Sample Request:
```bash
curl -X POST "http://localhost:8000/appointment/schedule/text" \
  -H "Content-Type: application/json" \
  -d '{"text": "Book me an appointment tomorrow"}'
```

#### Expected Response:
```json
{
  "step4_appointment": {
    "appointment": null,
    "status": "needs_clarification",
    "message": "Ambiguous date/time or department"
  }
}
```

---

### 4. Modular Debug Endpoints (For Grading Transparency)
- `POST /debug/step1-ocr` — Test text or image OCR extraction in isolation.
- `POST /debug/step2-extract` — Test LLM entity extraction in isolation.
- `POST /debug/step3-normalize` — Test date/time normalization in isolation.

---

## 🧪 Running Tests

Execute the automated test suite covering unit tests, department normalization, guardrails, and API integration:
```bash
python -c "import tests.test_pipeline as t; t.test_ocr_text_passthrough(); t.test_ocr_text_empty(); t.test_heuristic_entity_extraction_happy_path(); t.test_heuristic_entity_extraction_missing_fields(); t.test_heuristic_normalization(); t.test_department_normalization(); t.test_consolidation_success(); t.test_consolidation_guardrail_missing_department(); t.test_api_schedule_text_endpoint(); t.test_api_ambiguous_text_triggers_guardrail(); print('All tests passed!')"
```
Or with pytest:
```bash
pytest -v
```

---

## 📮 Postman Collection
Import `postman_collection.json` located in the root directory into Postman to test all endpoints with pre-configured requests.

---

## 🌐 Public Demo via ngrok
```bash
# Expose port 8000
ngrok http 8000
```
Use the generated HTTPS URL (e.g. `https://your-domain.ngrok-free.app/docs`) for live evaluation.
