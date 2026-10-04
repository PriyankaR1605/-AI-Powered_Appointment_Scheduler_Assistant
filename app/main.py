from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import health_router, appointment_router, debug_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Backend service that parses natural language or document-based appointment "
        "requests and converts them into structured scheduling data via a 4-step pipeline: "
        "OCR ➔ Entity Extraction ➔ Normalization ➔ Guardrails & Final Appointment."
    ),
    version=settings.PROJECT_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for browser-based testing and clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health_router)
app.include_router(appointment_router)
app.include_router(debug_router)

@app.get("/", tags=["Root"])
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "status": "online",
        "documentation": "/docs",
        "endpoints": {
            "text_pipeline": "POST /appointment/schedule/text",
            "image_pipeline": "POST /appointment/schedule/image",
            "debug_step1": "POST /debug/step1-ocr",
            "debug_step2": "POST /debug/step2-extract",
            "debug_step3": "POST /debug/step3-normalize",
            "health_check": "GET /health"
        }
    }
