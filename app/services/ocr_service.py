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


def _configure_tesseract():
    """Configure Tesseract executable path if available."""
    if not PYTESSERACT_AVAILABLE:
        return False
    
    # 1. Check custom path from config / .env
    custom_path = settings.TESSERACT_PATH
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
    if not PYTESSERACT_AVAILABLE or not _configure_tesseract():
        raise RuntimeError(
            "Tesseract OCR is not configured or executable not found. "
            "Please ensure Tesseract is installed and path is set in .env as TESSERACT_PATH."
        )

    try:
        # Load image from bytes
        raw_image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise ValueError(f"Invalid image format or corrupted file: {str(e)}")

    # Preprocess image
    processed_image = preprocess_image(raw_image)

    # Run Tesseract with word-level confidence data
    # --psm 6 assumes a single uniform block of text (standard for notes/emails)
    data = pytesseract.image_to_data(
        processed_image,
        output_type=pytesseract.Output.DICT,
        config="--psm 6"
    )

    words = []
    confidences = []

    for word, conf in zip(data["text"], data["conf"]):
        clean_word = word.strip()
        # conf is -1 when Tesseract encounters non-word boundary
        if clean_word and conf != -1:
            words.append(clean_word)
            confidences.append(float(conf))

    if not words:
        # Retry with automatic page segmentation mode (--psm 3) if --psm 6 found nothing
        data = pytesseract.image_to_data(
            processed_image,
            output_type=pytesseract.Output.DICT,
            config="--psm 3"
        )
        for word, conf in zip(data["text"], data["conf"]):
            clean_word = word.strip()
            if clean_word and conf != -1:
                words.append(clean_word)
                confidences.append(float(conf))

    raw_text = " ".join(words)
    
    # Calculate average confidence normalized to 0.0 - 1.0
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        # Tesseract confidence is 0 to 100
        normalized_conf = round(min(max(avg_conf / 100.0, 0.0), 1.0), 2)
    else:
        normalized_conf = 0.0

    return OCRResponse(raw_text=raw_text, confidence=normalized_conf)
