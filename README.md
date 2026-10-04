# 🗓️ AI-Powered Appointment Scheduler Assistant

A resilient, production-ready backend service that parses natural language text and document/image-based appointment requests into structured scheduling data following strict JSON schemas.

Developed for **Problem Statement 1: AI-Powered Appointment Scheduler Assistant** (Plum Benefits Assignment).

---

## 📑 Table of Contents
1. [Overview & Key Features](#-overview--key-features)
2. [Architecture & 4-Step Pipeline](#-architecture--4-step-pipeline)
3. [Project Directory Structure](#-project-directory-structure)
4. [Tech Stack](#-tech-stack)
5. [Prerequisites & Installation](#-prerequisites--installation)
6. [Environment Configuration](#-environment-configuration)
7. [Running the Application](#-running-the-application)
8. [API Endpoints & Usage Examples](#-api-endpoints--usage-examples)
   - [1. Schedule Appointment via Text](#1-schedule-appointment-via-text-happy-path)
   - [2. Schedule Appointment via Image OCR](#2-schedule-appointment-via-image-ocr)
   - [3. Guardrail Handling (Ambiguous / Missing Details)](#3-guardrail-handling-ambiguous--missing-details)
   - [4. Health Check Endpoint](#4-health-check-endpoint)
   - [5. Modular Debug Endpoints](#5-modular-debug-endpoints)
9. [Testing Suite](#-testing-suite)
10. [Postman Collection](#-postman-collection)
11. [Public Demo & Tunneling (ngrok)](#-public-demo--tunneling-ngrok)
12. [Design Decisions & Reliability](#-design-decisions--reliability)

---

## 🌟 Overview & Key Features

- **Dual Input Modality**: Handles both raw natural language text (chat, message) and scanned/photographed document images (notes, appointment cards, handwritten slips).
- **Automated Image OCR**: Preprocesses images using **Pillow** (grayscale, contrast adjustment, sharpening) and extracts text using **Tesseract OCR**.
- **LLM-Powered Entity Extraction**: Utilizes **Google Gemini 1.5 Flash** with strict JSON schemas to accurately extract `date_phrase`, `time_phrase`, and `department`.
- **Zero-Downtime Heuristic Fallback**: Includes a rule-based fallback entity extractor and normalizer to ensure 100% service uptime even without an internet connection or Gemini API key.
- **Strict Temporal Normalization**: Automatically anchors relative dates (`"next Friday"`, `"tomorrow"`, `"day after tomorrow"`) and 12h/24h times (`"3pm"`, `"14:30"`) to ISO 8601 calendar date (`YYYY-MM-DD`) and clock time (`HH:MM`) strictly in **Asia/Kolkata (IST)** timezone.
- **Department Normalization**: Standardizes medical department variants (e.g., *"teeth"* / *"dentist"* ➔ `Dentistry`, *"heart"* / *"cardiologist"* ➔ `Cardiology`, *"skin"* ➔ `Dermatology`).
- **Comprehensive Guardrails**: Evaluates confidence scores and missing mandatory fields; seamlessly returns `status: "needs_clarification"` when requests are ambiguous or incomplete.
- **Full Transparency Response**: Exposes outputs and confidence metrics from every intermediate pipeline stage (`step1_ocr`, `step2_extraction`, `step3_normalization`, `step4_appointment`).

---

## 🏗️ Architecture & 4-Step Pipeline

```
                     [ User Input ]
              (Typed Text or Image Upload)
                           │
                           ▼
 ┌─────────────────────────────────────────────────────────┐
 │ STEP 1: Ingestion & OCR / Text Extraction               │
 │  • Text Mode: Sanitized passthrough (Confidence: ~0.99) │
 │  • Image Mode: PIL Preprocessing ➔ Tesseract OCR Engine │
 └─────────────────────────┬───────────────────────────────┘
                           │ Output: raw_text, confidence
                           ▼
 ┌─────────────────────────────────────────────────────────┐
 │ STEP 2: Entity Extraction (Google Gemini 1.5 Flash)     │
 │  • Extracts: date_phrase, time_phrase, department       │
 │  • Offline Fallback: Heuristic regex entity parser      │
 │  • Assigns: entities_confidence                         │
 └─────────────────────────┬───────────────────────────────┘
                           │ Output: entities, entities_confidence
                           ▼
 ┌─────────────────────────────────────────────────────────┐
 │ STEP 3: Normalization Engine (Asia/Kolkata Timezone)    │
 │  • Dynamic Reference Time: Current IST anchor           │
 │  • Relative Dates & Clock ➔ ISO 8601 Date & 24h Time    │
 │  • Department Normalization (e.g. dentist ➔ Dentistry)  │
 │  • Assigns: normalization_confidence                    │
 └─────────────────────────┬───────────────────────────────┘
                           │ Output: normalized date, time, tz
                           ▼
 ┌─────────────────────────────────────────────────────────┐
 │ STEP 4: Guardrails & Final Consolidation Layer          │
 │  • Validates required fields (department, date, time)   │
 │  • Confidence checks (Confidence Threshold: >= 0.60)    │
 │  • Ambiguity detection                                  │
 │         │                               │               │
 │    [GUARDRAIL TRIGGERED]             [VALID]            │
 │         │                               │               │
 │         ▼                               ▼               │
 │  4a: EXIT CONDITION           4b: FINAL APPOINTMENT     │
 │  {                            {                         │
 │    "status":                    "appointment": {        │
 │      "needs_clarification",       "department": ...,    │
 │    "message": "..."               "date": "YYYY-MM-DD", │
 │  }                                "time": "HH:MM",      │
 │                                   "tz": "Asia/Kolkata"  │
 │                                 },                      │
 │                                 "status": "ok"          │
 │                               }                         │
 └─────────────────────────────────────────────────────────┘
```

---

## 📁 Project Directory Structure

```
Plum_Benifites_Assignment/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entrypoint & middleware
│   ├── config.py                    # Environment settings and configuration
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py               # Pydantic v2 request/response schemas
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── appointment.py           # /appointment/schedule/* & /debug/* endpoints
│   │   └── health.py                # /health endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ocr_service.py           # Text sanitization & Tesseract OCR engine
│   │   ├── extraction_service.py    # Google Gemini 1.5 Flash extraction & fallback
│   │   ├── normalization_service.py # IST datetime normalization logic
│   │   └── appointment_service.py   # Step 4 consolidation & guardrails
│   └── utils/
│       ├── __init__.py
│       ├── department_map.py        # Department canonical name mapping
│       └── guardrails.py            # Guardrail validation rules & thresholds
├── sample_data/
│   └── appointment_note.png         # Sample appointment note for image OCR testing
├── tests/
│   ├── __init__.py
│   ├── test_health.py               # Health endpoint test suite
│   └── test_pipeline.py             # Unit & integration tests for Steps 1-4
├── .env.example                     # Sample environment variable configuration
├── .gitignore                       # Git ignore patterns
├── postman_collection.json          # Complete Postman API collection
├── pytest.ini                       # Pytest configuration
├── README.md                        # Project documentation
└── requirements.txt                 # Python dependencies
```

---

## ⚡ Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| **Web Framework** | FastAPI | High-performance asynchronous REST API with auto-generated OpenAPI / Swagger documentation |
| **Validation & Schema** | Pydantic v2 | Strict JSON schema definitions, input validation, and data serialization |
| **LLM Reasoning** | Google Gemini 1.5 Flash | Zero-shot natural language understanding and entity extraction with structured JSON schemas |
| **Image Processing & OCR** | Pillow + Tesseract OCR | Image enhancement (contrast, grayscale, sharpening) and optical character recognition |
| **Timezone Management** | pytz | Strict anchoring to `Asia/Kolkata` (IST, UTC+05:30) |
| **Testing** | Pytest + HTTPX TestClient | Comprehensive unit and end-to-end integration testing |
| **Server** | Uvicorn | ASGI production server |

---

## 📋 Prerequisites & Installation

### 1. Prerequisites
- **Python**: Version `3.10` or higher
- **Git** installed on your machine
- *(Optional for Image OCR)* **Tesseract OCR**:
  - **Windows**: Download installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and install to `C:\Program Files\Tesseract-OCR\`.
  - **Linux / Ubuntu**: `sudo apt update && sudo apt install -y tesseract-ocr`
  - **macOS**: `brew install tesseract`

### 2. Clone the Repository
```bash
git clone https://github.com/PriyankaR1605/-AI-Powered_Appointment_Scheduler_Assistant.git
cd -AI-Powered_Appointment_Scheduler_Assistant
```

### 3. Create & Activate Virtual Environment
- **On Windows (PowerShell / CMD):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```
- **On Linux / macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## ⚙️ Environment Configuration

Create your `.env` file from `.env.example`:

- **On Linux / macOS:**
  ```bash
  cp .env.example .env
  ```
- **On Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```

Open `.env` and set your configuration:

```env
# Google Gemini API Key (Get a free key from https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key_here

# Path to Tesseract OCR executable
# Windows default:
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
# Linux default: /usr/bin/tesseract
# macOS default: /opt/homebrew/bin/tesseract

# Target Timezone (Default: Asia/Kolkata)
DEFAULT_TIMEZONE=Asia/Kolkata

# Confidence threshold for Guardrails (0.0 - 1.0)
CONFIDENCE_THRESHOLD=0.60

# Server settings
HOST=0.0.0.0
PORT=8000
DEBUG=True
```

> **Note**: If `GEMINI_API_KEY` is omitted or empty, the application automatically falls back to its built-in heuristic NLP engine, ensuring 100% uptime for offline grading and testing.

---

## 🚀 Running the Application

Start the FastAPI application using `uvicorn`:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running, access:
- **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 📡 API Endpoints & Usage Examples

### 1. Schedule Appointment via Text (Happy Path)
Processes natural language text through the full 4-step pipeline.

- **URL**: `POST /appointment/schedule/text`
- **Headers**: `Content-Type: application/json`

#### cURL Request:
```bash
curl -X POST "http://localhost:8000/appointment/schedule/text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Book dentist next Friday at 3pm"
  }'
```

#### JSON Response (`200 OK`):
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
    "entities_confidence": 0.95
  },
  "step3_normalization": {
    "normalized": {
      "date": "2026-10-09",
      "time": "15:00",
      "tz": "Asia/Kolkata"
    },
    "normalization_confidence": 0.95
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

### 2. Schedule Appointment via Image OCR
Uploads an image (PNG, JPG, JPEG) to extract text via Tesseract OCR and run through the appointment pipeline.

- **URL**: `POST /appointment/schedule/image`
- **Headers**: `Content-Type: multipart/form-data`

#### cURL Request:
```bash
curl -X POST "http://localhost:8000/appointment/schedule/image" \
  -F "file=@sample_data/appointment_note.png"
```

#### JSON Response (`200 OK`):
```json
{
  "step1_ocr": {
    "raw_text": "Dentist appointment next Friday at 3pm",
    "confidence": 0.88
  },
  "step2_extraction": {
    "entities": {
      "date_phrase": "next Friday",
      "time_phrase": "3pm",
      "department": "Dentist"
    },
    "entities_confidence": 0.92
  },
  "step3_normalization": {
    "normalized": {
      "date": "2026-10-09",
      "time": "15:00",
      "tz": "Asia/Kolkata"
    },
    "normalization_confidence": 0.95
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

### 3. Guardrail Handling (Ambiguous / Missing Details)
When mandatory fields are missing or confidence is low, the pipeline enters the exit condition with `status: "needs_clarification"`.

- **URL**: `POST /appointment/schedule/text`
- **Headers**: `Content-Type: application/json`

#### cURL Request:
```bash
curl -X POST "http://localhost:8000/appointment/schedule/text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Schedule an appointment tomorrow"
  }'
```

#### JSON Response (`200 OK`):
```json
{
  "step1_ocr": {
    "raw_text": "Schedule an appointment tomorrow",
    "confidence": 0.99
  },
  "step2_extraction": {
    "entities": {
      "date_phrase": "tomorrow",
      "time_phrase": null,
      "department": null
    },
    "entities_confidence": 0.5
  },
  "step3_normalization": {
    "normalized": {
      "date": "2026-10-05",
      "time": null,
      "tz": "Asia/Kolkata"
    },
    "normalization_confidence": 0.5
  },
  "step4_appointment": {
    "appointment": null,
    "status": "needs_clarification",
    "message": "Ambiguous date/time or department: missing department, missing time"
  }
}
```

---

### 4. Health Check Endpoint
Quickly verify service health, active timezone, and version.

- **URL**: `GET /health`

#### cURL Request:
```bash
curl -X GET "http://localhost:8000/health"
```

#### JSON Response (`200 OK`):
```json
{
  "status": "healthy",
  "service": "AI-Powered Appointment Scheduler Assistant",
  "version": "1.0.0",
  "timezone": "Asia/Kolkata"
}
```

---

### 5. Modular Debug Endpoints
Allow evaluators to inspect each stage of the pipeline independently:

| Endpoint | Method | Input | Description |
|---|---|---|---|
| `/debug/step1-ocr` | `POST` | `file` (image) or `text` (form) | Test Step 1 text sanitization or Tesseract OCR extraction |
| `/debug/step2-extract` | `POST` | `raw_text` (form) | Test Step 2 Gemini LLM entity extraction |
| `/debug/step3-normalize` | `POST` | `date_phrase`, `time_phrase` (form) | Test Step 3 IST date & time normalization |

---

## 🧪 Testing Suite

Automated unit and integration tests are provided under [`tests/`](file:///D:/Projects/Plum_Benifites_Assignment/tests).

### Run all tests with pytest:
```bash
pytest -v
```

### Test Coverage Highlights:
- ✅ **Step 1 Tests**: Text passthrough sanitization, empty text handling, OCR error trapping.
- ✅ **Step 2 Tests**: Happy path entity extraction, missing field extraction, confidence scoring.
- ✅ **Step 3 Tests**: Relative date conversion (`tomorrow`, `next Friday`), 12h/24h time conversions, IST timezone validation.
- ✅ **Department Normalization Tests**: Mapping synonyms to standard clinical departments (`dentist` ➔ `Dentistry`, `skin` ➔ `Dermatology`, `heart` ➔ `Cardiology`).
- ✅ **Step 4 & Guardrail Tests**: Validation of complete appointments, handling missing departments/times, triggering `needs_clarification`.
- ✅ **API Integration Tests**: Full end-to-end request/response validation against FastAPI endpoints.

---

## 📮 Postman Collection

A ready-to-import Postman collection is included: [`postman_collection.json`](file:///D:/Projects/Plum_Benifites_Assignment/postman_collection.json).

### How to use:
1. Open **Postman**.
2. Click **Import** in the top left corner.
3. Select `postman_collection.json` from the root directory.
4. Set the environment variable `baseUrl` to `http://localhost:8000` (or your ngrok URL).
5. Run the pre-configured requests for text scheduling, image upload, debug steps, and guardrails.

---

## 🌐 Public Demo & Tunneling (ngrok)

To share or evaluate the live API remotely:

```bash
# Start your local server
uvicorn app.main:app --port 8000

# In a separate terminal, expose port 8000
ngrok http 8000
```

Use the generated public URL (e.g., `https://xxxx-xx-xx.ngrok-free.app/docs`) to access the interactive Swagger documentation and test live requests.

---

## 🧠 Design Decisions & Reliability

1. **Temporal Reference Anchoring**:
   - Because relative phrases like `"next Friday"` depend on the current calendar day, the service anchors all computations dynamically to the current timestamp in `Asia/Kolkata` (IST).
2. **Deterministic Schemas**:
   - Pydantic models enforce exact field constraints (`YYYY-MM-DD` date strings, `HH:MM` 24-hour time strings, and `tz: "Asia/Kolkata"`).
3. **Dual-Layer Robustness**:
   - If Google Gemini API is throttled, rate-limited, or unavailable, the system automatically falls back to an offline regex & heuristic parser, preventing any API 500 crashes.
4. **Transparent Step Outputs**:
   - The primary `/appointment/schedule/*` endpoints return the full breakdown of all 4 pipeline steps, enabling developers and evaluators to trace how inputs are transformed at every stage.
