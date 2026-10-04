import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of Project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "AI-Powered Appointment Scheduler Assistant"
    PROJECT_VERSION: str = "1.0.0"
    
    # API Keys & Paths
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    TESSERACT_PATH: str = os.getenv(
        "TESSERACT_PATH", 
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
    
    # Timezone & Defaults
    DEFAULT_TIMEZONE: str = os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.60"))
    
    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

settings = Settings()
