import io
import os
import shutil
import logging
from typing import Optional
from PIL import Image, ImageEnhance, ImageFilter
from app.models.schemas import OCRResponse
from app.config import settings

logger = logging.getLogger(__name__)

# Try importing pytesseract
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    logger.warning("pytesseract is not installed. Image OCR will be unavailable until installed.")


def _configure_tesseract() -> bool:
    """Configure Tesseract executable path if available."""
    if not PYTESSERACT_AVAILABLE:
        return False
    
    # 1. Check custom path from config / .env
    custom_path = (settings.TESSERACT_PATH or "").strip()
    if custom_path and os.path.isfile(custom_path):
        pytesseract.pytesseract.tesseract_cmd = custom_path
        return True
    
    # 2. Check system PATH
    system_tesseract = shutil.which("tesseract")
    if system_tesseract:
        pytesseract.pytesseract.tesseract_cmd = system_tesseract
        return True
        
    # 3. Check common Windows installation locations
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for p in common_paths:
        if os.path.isfile(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
            
    return False


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Apply image preprocessing to maximize OCR accuracy on noisy or scanned notes:
    - Grayscale conversion
    - Contrast enhancement
    - Sharpening filter
    """
    # 1. Convert to grayscale
    img_gray = image.convert("L")
    
    # 2. Boost contrast
    enhancer = ImageEnhance.Contrast(img_gray)
    img_contrast = enhancer.enhance(2.0)
    
    # 3. Apply sharpening
    img_sharp = img_contrast.filter(ImageFilter.SHARPEN)
    
    return img_sharp


def extract_text_from_string(text: str) -> OCRResponse:
    """
    Step 1 for typed natural language requests.
    Direct passthrough with sanitization and high confidence.
    
    Example:
        Input: "Book dentist next Friday at 3pm"
        Output: OCRResponse(raw_text="Book dentist next Friday at 3pm", confidence=0.99)
    """
    sanitized = text.strip()
    # If text is empty or only whitespace, return 0.0 confidence
    if not sanitized:
        return OCRResponse(raw_text="", confidence=0.0)
    
    return OCRResponse(raw_text=sanitized, confidence=0.99)


def extract_text_from_image(image_bytes: bytes) -> OCRResponse:
    """
    Step 1 for image inputs (photos, scanned notes, receipts).
    Preprocesses the image with PIL and runs Tesseract OCR.
    
    Computes confidence score based on word-level OCR confidence.
    """
    is_configured = _configure_tesseract()

    if not is_configured:
        # Intelligent fallback to Gemini Vision if Tesseract binary is not installed
        api_key = (settings.GEMINI_API_KEY or "").strip()
        if api_key:
            for model_name in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    vision_model = genai.GenerativeModel(model_name)
                    raw_image = Image.open(io.BytesIO(image_bytes))
                    response = vision_model.generate_content([
                        "You are an OCR assistant. Transcribe and extract all readable text verbatim from this appointment note or image. Return ONLY the plain text content without markdown or conversation.",
                        raw_image
                    ])
                    extracted = response.text.strip()
                    if extracted:
                        return OCRResponse(raw_text=extracted, confidence=0.92)
                except Exception as e:
                    logger.warning(f"Gemini vision fallback with {model_name} failed: {e}")

        raise RuntimeError(
            "Tesseract OCR is not configured or executable not found at C:\\Program Files\\Tesseract-OCR\\tesseract.exe. "
            "Please ensure Tesseract is installed and path is set in .env as TESSERACT_PATH."
        )

    try:
        # Load image from bytes
        raw_image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise ValueError(f"Invalid image format or corrupted file: {str(e)}")

    # 1. Primary OCR extraction on raw image
    extracted_text = pytesseract.image_to_string(raw_image).strip()

    # 2. If raw image yielded empty text, retry on preprocessed image
    if not extracted_text:
        processed_image = preprocess_image(raw_image)
        extracted_text = pytesseract.image_to_string(processed_image).strip()
        target_img = processed_image
    else:
        target_img = raw_image

    # 3. Calculate word-level confidence from Tesseract
    confidences = []
    try:
        data = pytesseract.image_to_data(
            target_img,
            output_type=pytesseract.Output.DICT,
            config="--psm 6"
        )
        for word, conf in zip(data.get("text", []), data.get("conf", [])):
            if str(word).strip() and conf != -1:
                confidences.append(float(conf))
    except Exception:
        pass

    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        normalized_conf = round(min(max(avg_conf / 100.0, 0.0), 1.0), 2)
    elif extracted_text:
        normalized_conf = 0.85
    else:
        normalized_conf = 0.0

    return OCRResponse(raw_text=extracted_text, confidence=normalized_conf)
