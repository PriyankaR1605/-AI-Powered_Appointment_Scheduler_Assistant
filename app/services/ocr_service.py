import io
import os
import shutil
import logging
from typing import Optional, List
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from app.models.schemas import OCRResponse
from app.config import settings

logger = logging.getLogger(__name__)

# Try importing pytesseract
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    logger.warning("pytesseract is not installed. Image OCR will rely on Gemini Vision.")

VISION_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
]


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


def preprocess_image(image: Image.Image) -> List[Image.Image]:
    """
    Apply multiple image preprocessing variants to maximize OCR accuracy:
    1. EXIF orientation correction
    2. RGB conversion (removes transparency/alpha artifacts)
    3. Upscaling if image is small (< 1000px)
    4. Grayscale + contrast enhancement + sharpening
    5. Adaptive binarization / thresholding for low-contrast notes
    """
    # 1. EXIF orientation correction
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass

    # 2. Convert to RGB if RGBA/P/CMYK
    if image.mode in ("RGBA", "P", "LA", "CMYK"):
        bg = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "RGBA":
            bg.paste(image, mask=image.split()[3])
            image = bg
        else:
            image = image.convert("RGB")
    elif image.mode != "RGB":
        image = image.convert("RGB")

    # 3. Upscale small images to improve Tesseract character recognition
    w, h = image.size
    if max(w, h) < 1200:
        scale = max(2.0, 1200.0 / max(w, h))
        image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    variants = [image]

    # Variant 1: Grayscale + High Contrast + Sharpening
    img_gray = image.convert("L")
    enhancer = ImageEnhance.Contrast(img_gray)
    img_contrast = enhancer.enhance(2.2)
    img_sharp = img_contrast.filter(ImageFilter.SHARPEN)
    variants.append(img_sharp)

    # Variant 2: Thresholded binary (B&W) for handwritten/sticky notes
    threshold = 140
    img_binary = img_gray.point(lambda p: 255 if p > threshold else 0, mode="1")
    variants.append(img_binary)

    return variants


def _extract_with_gemini_vision(image_bytes: bytes) -> Optional[OCRResponse]:
    """Fallback / Multimodal extractor using Google Gemini Vision."""
    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        raw_image = Image.open(io.BytesIO(image_bytes))
        try:
            raw_image = ImageOps.exif_transpose(raw_image)
        except Exception:
            pass

        for model_name in VISION_MODELS:
            try:
                vision_model = genai.GenerativeModel(model_name)
                response = vision_model.generate_content([
                    "You are an OCR transcription engine. Transcribe and extract all readable text verbatim from this appointment note, document, or image. Return ONLY the plain text content without any markdown fences, extra commentary, or conversational phrases.",
                    raw_image
                ], request_options={"timeout": 10})
                extracted = response.text.strip()
                if extracted:
                    return OCRResponse(raw_text=extracted, confidence=0.95)
            except Exception as e:
                logger.warning(f"Gemini vision with {model_name} failed: {e}")
                continue
    except Exception as e:
        logger.warning(f"Gemini vision extraction failed completely: {e}")

    return None


def extract_text_from_string(text: str) -> OCRResponse:
    """
    Step 1 for typed natural language requests.
    Direct passthrough with sanitization and high confidence.
    """
    sanitized = text.strip()
    if not sanitized:
        return OCRResponse(raw_text="", confidence=0.0)
    
    return OCRResponse(raw_text=sanitized, confidence=0.99)


def extract_text_from_image(image_bytes: bytes) -> OCRResponse:
    """
    Step 1 for image inputs (photos, scanned notes, receipts).
    Uses a hybrid approach:
    1. Preprocesses image and runs Tesseract OCR across multiple PSM modes.
    2. If Tesseract output is empty or poor, falls back to Gemini Vision.
    """
    try:
        raw_image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise ValueError(f"Invalid image format or corrupted file: {str(e)}")

    best_text = ""
    best_conf = 0.0

    is_tesseract_configured = _configure_tesseract()
    if is_tesseract_configured:
        variants = preprocess_image(raw_image)
        
        # Test configurations: PSM 3 (auto), PSM 6 (uniform block), PSM 11 (sparse text)
        psm_modes = ["--psm 6", "--psm 3", "--psm 11"]
        
        for img_variant in variants:
            for psm in psm_modes:
                try:
                    text = pytesseract.image_to_string(img_variant, config=psm).strip()
                    if len(text) > len(best_text):
                        # Calculate confidence
                        data = pytesseract.image_to_data(
                            img_variant,
                            output_type=pytesseract.Output.DICT,
                            config=psm
                        )
                        confidences = [
                            float(c) for w, c in zip(data.get("text", []), data.get("conf", []))
                            if str(w).strip() and c != -1
                        ]
                        conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.80
                        best_text = text
                        best_conf = round(min(max(conf, 0.0), 1.0), 2)
                except Exception:
                    continue

    # If Tesseract returned good text with reasonable length/confidence, return it
    alphanumeric_chars = sum(1 for c in best_text if c.isalnum())
    if best_text and alphanumeric_chars >= 5 and best_conf >= 0.50:
        return OCRResponse(raw_text=best_text, confidence=best_conf)

    # Fallback to Gemini Vision if Tesseract was unavailable, empty, or low confidence
    vision_res = _extract_with_gemini_vision(image_bytes)
    if vision_res and vision_res.raw_text:
        return vision_res

    # If Tesseract produced some text even if low confidence, return it rather than failing
    if best_text:
        return OCRResponse(raw_text=best_text, confidence=max(best_conf, 0.50))

    if not is_tesseract_configured:
        raise RuntimeError(
            "Tesseract OCR is not configured and Gemini Vision was unavailable. "
            "Please ensure Tesseract is installed or GEMINI_API_KEY is configured in .env."
        )

    return OCRResponse(raw_text="", confidence=0.0)

