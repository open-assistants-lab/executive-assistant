"""OCR tools for extracting text from images and PDFs."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool

from cassey.config import create_model
from cassey.config.settings import settings
from cassey.storage.file_sandbox import SecurityError, get_sandbox

_OCR_ENGINE: Any | None = None
_OCR_ENGINE_NAME: str | None = None


def _validate_ocr_path(file_path: str) -> Path:
    sandbox = get_sandbox()
    try:
        validated = sandbox._validate_path(file_path)
    except SecurityError as e:
        raise ValueError(f"Security error: {e}") from e

    if not validated.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if validated.is_dir():
        raise ValueError(f"Path is a directory, expected a file: {file_path}")

    size_mb = validated.stat().st_size / (1024 * 1024)
    if size_mb > settings.OCR_MAX_FILE_MB:
        raise ValueError(
            f"File too large for OCR ({size_mb:.2f}MB > {settings.OCR_MAX_FILE_MB}MB)."
        )

    return validated


def _load_paddleocr() -> Any:
    try:
        from paddleocr import PaddleOCR
    except Exception as e:
        raise RuntimeError(
            "PaddleOCR is not installed. Install with: pip install paddleocr paddlepaddle"
        ) from e

    return PaddleOCR(
        use_angle_cls=True,
        lang=settings.OCR_LANG,
        show_log=False,
        use_gpu=settings.OCR_USE_GPU,
    )


def _load_surya() -> Any:
    """Load Surya OCR predictors."""
    try:
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor
    except Exception as e:
        raise RuntimeError(
            "Surya is not installed. Install with: pip install surya-ocr"
        ) from e

    foundation = FoundationPredictor()
    recognition = RecognitionPredictor(foundation)
    detection = DetectionPredictor()
    return {"recognition": recognition, "detection": detection}


def _get_ocr_engine() -> tuple[str, Any | None]:
    global _OCR_ENGINE, _OCR_ENGINE_NAME
    engine = settings.OCR_ENGINE.lower().strip()
    if _OCR_ENGINE is not None and _OCR_ENGINE_NAME == engine:
        return engine, _OCR_ENGINE

    if engine == "paddleocr":
        _OCR_ENGINE = _load_paddleocr()
        _OCR_ENGINE_NAME = engine
        return engine, _OCR_ENGINE

    if engine == "surya":
        _OCR_ENGINE = _load_surya()
        _OCR_ENGINE_NAME = engine
        return engine, _OCR_ENGINE

    if engine == "tesseract":
        _OCR_ENGINE = None
        _OCR_ENGINE_NAME = engine
        return engine, None

    raise ValueError(f"Unknown OCR engine: {settings.OCR_ENGINE}")


def _format_paddle_result(result: list, output_format: str) -> str:
    if not result or not result[0]:
        return "No text detected in image."

    if output_format == "json":
        formatted = []
        for line in result[0]:
            bbox = line[0]
            text_info = line[1]
            formatted.append(
                {
                    "text": text_info[0],
                    "confidence": text_info[1],
                    "bbox": bbox,
                }
            )
        return json.dumps(formatted, indent=2)

    lines = [line[1][0] for line in result[0]]
    return "\n".join(lines)


def _run_tesseract(path: Path) -> str:
    cmd = [
        "tesseract",
        str(path),
        "stdout",
        "-l",
        settings.OCR_LANG,
    ]
    try:
        completed = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.OCR_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as e:
        raise RuntimeError("Tesseract is not installed or not in PATH.") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("Tesseract timed out during OCR.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Tesseract failed: {e.stderr.strip()}") from e

    output = completed.stdout.strip()
    return output or "No text detected in image."


def _run_surya(path: Path, engines: dict) -> str:
    """Run Surya OCR on an image."""
    try:
        from PIL import Image
    except Exception as e:
        raise RuntimeError(f"Failed to import PIL: {e}") from e

    try:
        img = Image.open(path)
        recognition = engines["recognition"]
        detection = engines["detection"]

        # Run OCR with detection and recognition
        predictions = recognition([img], det_predictor=detection)

        if not predictions or len(predictions) == 0:
            return "No text detected in image."

        # Extract text from predictions
        text_lines = predictions[0].text_lines
        if not text_lines:
            return "No text detected in image."

        extracted_text = "\n".join([line.text for line in text_lines])
        return extracted_text or "No text detected in image."

    except Exception as e:
        raise RuntimeError(f"Surya OCR failed: {e}") from e


def _extract_pdf_text(path: Path, output_format: str) -> str:
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError("pypdf is required for PDF text extraction.") from e

    reader = PdfReader(str(path))
    max_pages = min(len(reader.pages), settings.OCR_MAX_PAGES)
    pages: list[dict[str, Any]] = []
    engine_name: str | None = None
    engine: Any | None = None
    fitz_doc: Any | None = None

    for idx in range(max_pages):
        text = reader.pages[idx].extract_text() or ""
        source = "text"

        if len(text.strip()) < settings.OCR_PDF_MIN_TEXT_CHARS:
            if engine_name is None:
                engine_name, engine = _get_ocr_engine()
            if fitz_doc is None:
                fitz_doc = _open_pymupdf_document(path)

            text = _ocr_pdf_page(fitz_doc, idx, engine_name, engine)
            source = "ocr"

        pages.append({"page": idx + 1, "text": text, "source": source})

    if fitz_doc is not None:
        fitz_doc.close()

    if output_format == "json":
        return json.dumps(pages, indent=2)

    combined = "\n\n".join(p["text"] for p in pages).strip()
    if not combined:
        return "No text found in PDF. Scanned PDFs require OCR image rendering support."
    return combined


def _open_pymupdf_document(path: Path) -> Any:
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        raise RuntimeError(
            "PyMuPDF is required to OCR scanned PDFs. Install with: pip install pymupdf"
        ) from e
    return fitz.open(str(path))


def _ocr_pdf_page(doc: Any, page_index: int, engine_name: str, engine: Any | None) -> str:
    page = doc.load_page(page_index)
    pix = page.get_pixmap(dpi=settings.OCR_PDF_DPI)

    if engine_name == "paddleocr":
        try:
            import numpy as np
        except Exception as e:
            raise RuntimeError("NumPy is required for PaddleOCR PDF rendering.") from e

        img = np.frombuffer(pix.samples, dtype=np.uint8)
        img = img.reshape(pix.height, pix.width, pix.n)
        if pix.n >= 3:
            img = img[:, :, :3]
        else:
            img = np.repeat(img, 3, axis=2)
        # PaddleOCR expects BGR
        img = img[:, :, ::-1]
        result = engine.ocr(img, cls=True)
        return _format_paddle_result(result, "text")

    if engine_name == "surya":
        try:
            from PIL import Image
            import io
        except Exception as e:
            raise RuntimeError(f"Failed to import PIL: {e}") from e

        # Convert pixmap to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        # Run Surya OCR
        recognition = engine["recognition"]
        detection = engine["detection"]
        predictions = recognition([img], det_predictor=detection)

        if predictions and len(predictions) > 0:
            text_lines = predictions[0].text_lines
            if text_lines:
                return "\n".join([line.text for line in text_lines])

        return "No text detected in PDF page."

    if engine_name == "tesseract":
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            pix.save(str(tmp_path))
            return _run_tesseract(tmp_path)
        finally:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass

    raise ValueError(f"Unsupported OCR engine for PDF: {engine_name}")


def choose_ocr_method(instruction: str, image_size_kb: int) -> str:
    instruction_lower = instruction.lower()

    if any(word in instruction_lower for word in ["table", "form", "receipt", "invoice", "json", "structured"]):
        return "vision"

    if image_size_kb > 500:
        return "local"

    if "extract" in instruction_lower and "json" not in instruction_lower:
        return "local"

    return "local"


def _ocr_extract_text_impl(image_path: str, output_format: str = "text") -> str:
    """Core OCR text extraction implementation."""
    try:
        validated = _validate_ocr_path(image_path)
        if validated.suffix.lower() == ".pdf":
            return _extract_pdf_text(validated, output_format)

        engine_name, engine = _get_ocr_engine()
        if engine_name == "paddleocr":
            result = engine.ocr(str(validated), cls=True)
            return _format_paddle_result(result, output_format)

        if engine_name == "surya":
            if output_format == "json":
                return "JSON output not supported for surya engine."
            return _run_surya(validated, engine)

        if engine_name == "tesseract":
            if output_format == "json":
                return "JSON output not supported for tesseract engine."
            return _run_tesseract(validated)

        return f"Unsupported OCR engine: {engine_name}"
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {e}"


@tool
def ocr_extract_text(image_path: str, output_format: str = "text") -> str:
    """
    Extract text from an image or PDF using local OCR.

    Args:
        image_path: Path to image/PDF file (relative to thread sandbox).
        output_format: "text" or "json".

    Returns:
        Extracted text or JSON with bounding boxes (if supported).
    """
    return _ocr_extract_text_impl(image_path, output_format)


async def _ocr_extract_structured_impl(image_path: str, instruction: str = "Extract structured data") -> str:
    """Core OCR structured extraction implementation."""
    try:
        validated = _validate_ocr_path(image_path)
        if validated.suffix.lower() == ".pdf":
            ocr_text = _extract_pdf_text(validated, output_format="text")
        else:
            ocr_text = _ocr_extract_text_impl(image_path, output_format="text")
        if ocr_text.startswith("Error:") or ocr_text.startswith("No text"):
            return ocr_text
    except Exception as e:
        return f"Error: {e}"

    system_prompt = (
        "You extract structured data from OCR text. "
        "Return ONLY valid JSON. No markdown, no extra commentary."
    )

    prompt = (
        f"Instruction: {instruction}\n\n"
        "OCR text:\n"
        f"{ocr_text}\n\n"
        "Return JSON only."
    )

    try:
        model = create_model(
            provider=settings.OCR_STRUCTURED_PROVIDER,
            model=settings.OCR_STRUCTURED_MODEL,
            temperature=0.0,
        )
    except Exception as e:
        return f"Error: {e}"

    last_error = None
    for attempt in range(settings.OCR_STRUCTURED_MAX_RETRIES + 1):
        try:
            response = await model.ainvoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
            )
            content = response.content if hasattr(response, "content") else str(response)
            parsed = json.loads(content)
            return json.dumps(parsed, indent=2)
        except Exception as e:
            last_error = e
            prompt = (
                f"Your previous output was invalid JSON. Fix it.\n"
                f"Error: {e}\n\n"
                f"Instruction: {instruction}\n"
                "Return ONLY valid JSON."
            )

    return f"Error: Failed to produce valid JSON after retries ({last_error})"


@tool
async def ocr_extract_structured(image_path: str, instruction: str = "Extract structured data") -> str:
    """
    Extract structured data using local OCR + LLM formatting.

    Args:
        image_path: Path to image/PDF file (relative to thread sandbox).
        instruction: What to extract.

    Returns:
        JSON string.
    """
    return await _ocr_extract_structured_impl(image_path, instruction)


@tool
async def extract_from_image(
    image_path: str,
    instruction: str = "Extract all text",
    method: str = "auto",
) -> str:
    """
    Extract text or structured data from an image using the best available method.

    Args:
        image_path: Path to image/PDF file (relative to thread sandbox).
        instruction: What to extract.
        method: "auto", "local", or "vision".

    Returns:
        Extracted text or structured JSON.
    """
    try:
        validated = _validate_ocr_path(image_path)
    except Exception as e:
        return f"Error: {e}"

    image_size_kb = validated.stat().st_size / 1024

    if method == "auto":
        method = choose_ocr_method(instruction, image_size_kb)

    if method == "local":
        return _ocr_extract_text_impl(image_path)
    if method == "vision":
        return await _ocr_extract_structured_impl(image_path, instruction)

    return f"Unknown method: {method}"


def get_ocr_tools() -> list[BaseTool]:
    """Get OCR tools."""
    return [ocr_extract_text, ocr_extract_structured, extract_from_image]
