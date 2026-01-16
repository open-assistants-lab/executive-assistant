# OCR Tool Design for Cassey

## Goal

Add OCR (Optical Character Recognition) capability to Cassey for extracting text from images, screenshots, scanned PDFs, and photos.

## Key Considerations

| Factor | Consideration |
|--------|---------------|
| **Privacy** | Local processing preferred over API |
| **Cost** | Free/local better than per-API costs |
| **Latency** | Fast enough for interactive use |
| **Accuracy** | Good for documents, receipts, screenshots |
| **Languages** | Support English + Chinese (essential for user) |
| **Deployment** | Lightweight, easy to Dockerize |

---

## OCR Library Comparison

| Library | Size | Speed | Accuracy | Languages | Notes |
|---------|------|-------|----------|-----------|-------|
| **PaddleOCR** | ~50MB | Fast | High | 80+ | Best overall, Chinese/English |
| **Tesseract** | ~20MB | Medium | High | 100+ | Classic, dependency-heavy |
| **RapidOCR** | ~10MB | Very Fast | Good | 20+ | Lightest, Paddle-based |
| **EasyOCR** | ~200MB | Slow | Very High | 70+ | Heavy, PyTorch dependency |
| **GPT-4o Vision** | 0MB (API) | Medium | Very High | All | Costs money, needs network |

---

## Recommendation: PaddleOCR

**Why PaddleOCR:**
- Baidu-maintained, actively developed
- Excellent Chinese + English support
- CPU-friendly, no GPU required
- Lightweight (~50MB models)
- Free and open source
- Fast enough for interactive use

---

## Tool Specifications

### 1. Basic OCR (PaddleOCR)

```python
@tool
def ocr_extract_text(
    image_path: str,
    output_format: str = "text"
) -> str:
    """
    Extract text from image using local OCR (PaddleOCR).

    Fast, free, runs locally. Great for:
    - Screenshots
    - Scanned documents
    - Receipts
    - Photos of text

    Args:
        image_path: Path to image file
        output_format: 'text' (default) or 'json' (with bounding boxes)

    Returns:
        Extracted text

    Example:
        ocr_extract_text("screenshot.png")
        ocr_extract_text("receipt.jpg", output_format="json")
    """
```

### 2. Structured OCR (PaddleOCR + LLM)

```python
@tool
def ocr_extract_structured(
    image_path: str,
    instruction: str = "Extract structured data"
) -> str:
    """
    Extract structured data from image using OCR + LLM.

    Combines PaddleOCR (fast text extraction) with LLM
    for structured output. Can use local LLM or API.

    Args:
        image_path: Path to image file
        instruction: What to extract (e.g., "Extract receipt items")

    Returns:
        Structured data as JSON

    Example:
        ocr_extract_structured("receipt.jpg", "Extract items, prices, and total")
    """
```

### 3. Hybrid Tool (Auto-select method)

```python
@tool
def extract_from_image(
    image_path: str,
    instruction: str = "Extract all text",
    method: str = "auto"
) -> str:
    """
    Extract text from image using best available method.

    Auto selection logic:
    - Use PaddleOCR for simple text extraction (fast, free)
    - Use vision model for structured data (tables, forms, reasoning)

    Args:
        image_path: Path to image file
        instruction: What to extract
        method: 'auto', 'local' (PaddleOCR), or 'vision' (GPT-4o)

    Returns:
        Extracted text or structured data
    """
```

---

## Implementation

### Core OCR Engine

```python
# src/cassey/tools/ocr_tool.py

from paddleocr import PaddleOCR
import os
from typing import Optional

# Lazy initialization
_ocr_engine: Optional[PaddleOCR] = None

def get_ocr_engine():
    """Get or create PaddleOCR instance (lazy load)."""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PaddleOCR(
            use_angle_cls=True,
            lang='en',  # or 'ch' for Chinese, 'fr' for French, etc.
            show_log=False,
            use_gpu=False  # Set True if GPU available
        )
    return _ocr_engine
```

### Basic Extraction

```python
@tool
def ocr_extract_text(
    image_path: str,
    output_format: str = "text"
) -> str:
    """Extract text from image using local OCR (PaddleOCR)."""

    if not os.path.exists(image_path):
        return f"Error: File not found: {image_path}"

    ocr = get_ocr_engine()
    result = ocr.ocr(image_path, cls=True)

    if result is None or result[0] is None:
        return "No text detected in image."

    if output_format == "json":
        import json
        formatted = []
        for line in result[0]:
            bbox = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            text_info = line[1]  # (text, confidence)
            formatted.append({
                "text": text_info[0],
                "confidence": text_info[1],
                "bbox": bbox
            })
        return json.dumps(formatted, indent=2)

    else:
        # Return plain text
        lines = [line[1][0] for line in result[0]]
        return "\n".join(lines)
```

### Auto-Selection Logic

```python
def choose_ocr_method(instruction: str, image_size_kb: int) -> str:
    """Choose between local OCR and vision model."""

    # Use local OCR if:
    # - Simple "extract text" request
    # - Large image (save API costs)
    # - No structured output needed

    instruction_lower = instruction.lower()

    # Simple text extraction → local OCR
    if "extract" in instruction_lower and "json" not in instruction_lower:
        return "local"

    # Large files → local OCR (save costs)
    if image_size_kb > 500:
        return "local"

    # Structured data → vision model
    if any(word in instruction_lower for word in ["table", "form", "receipt", "invoice", "json"]):
        return "vision"

    # Default to local OCR
    return "local"
```

---

## PaddleOCR Details

### Installation

```bash
# Basic installation
pip install paddleocr paddlepaddle

# For CPU only (lighter)
pip install paddlepaddle==2.6.0

# For GPU support (faster)
pip install paddlepaddle-gpu==2.6.0
```

### Language Support

```python
# English (default)
ocr = PaddleOCR(lang='en')

# Chinese
ocr = PaddleOCR(lang='ch')

# French
ocr = PaddleOCR(lang='fr')

# Multilingual
ocr = PaddleOCR(lang='en')  # Supports 80+ languages
```

### Result Format

```python
result = [
    [
        [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],  # Bounding box
        ('text_content', 0.95)  # Text and confidence
    ],
    # ... more lines
]
```

---

## Docker Deployment

### Dockerfile Additions

```dockerfile
# Install system dependencies for PaddleOCR
RUN apt-get update && apt-get install -y \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Install PaddleOCR and PaddlePaddle (CPU version)
RUN pip install paddleocr paddlepaddle==2.6.0
```

### docker-compose.yml

```yaml
services:
  cassey:
    build: .
    environment:
      - OCR_ENGINE=paddleocr
      - OCR_LANG=en
      - OCR_USE_GPU=false
    volumes:
      - ./models:/app/models  # Optional: cache models locally
```

### Image Size Impact

| Component | Size |
|-----------|------|
| Base image | ~500MB |
| PaddlePaddle | ~100MB |
| PaddleOCR models | ~50MB |
| **Total overhead** | **~150MB** |

---

## Comparison: PaddleOCR vs Vision Model

| Aspect | PaddleOCR | GPT-4o Vision |
|--------|-----------|---------------|
| **Cost** | Free (local) | ~$0.01-0.05/image |
| **Latency** | ~1-3 seconds | ~2-5 seconds |
| **Privacy** | 100% local | Data sent to OpenAI |
| **Accuracy** | Excellent for documents | Excellent for understanding |
| **Structured output** | No (raw text) | Yes (JSON, tables) |
| **Offline** | Yes | No |
| **Dependency** | +150MB image | None (API) |

---

## Hybrid Approach

```python
@tool
def extract_from_image(
    image_path: str,
    instruction: str = "Extract all text",
    method: str = "auto"
) -> str:
    """
    Extract text from image using best available method.

    Auto selection:
    - Simple text extraction → PaddleOCR (fast, free)
    - Structured data/tables → Vision model (accurate)
    - Large files → PaddleOCR (save costs)

    Args:
        image_path: Path to image file
        instruction: What to extract
        method: 'auto', 'local', or 'vision'
    """
    image_size_kb = os.path.getsize(image_path) / 1024

    # Determine method
    if method == "auto":
        method = choose_ocr_method(instruction, image_size_kb)

    # Execute with chosen method
    if method == "local":
        return ocr_extract_text(image_path)
    elif method == "vision":
        return vision_extract_from_image(image_path, instruction)
    else:
        return f"Unknown method: {method}"
```

---

## Use Cases

| Use Case | Recommended Method | Reason |
|----------|-------------------|--------|
| Screenshots | PaddleOCR | Fast, text extraction only |
| Scanned PDFs | PaddleOCR | Document OCR optimized |
| Receipts | Hybrid | OCR + LLM for structured output |
| Forms | Vision model | Table/form understanding |
| Photos of text | PaddleOCR | Mobile photo OCR |
| Handwriting | Vision model | Better at varied styles |
| Charts/Graphs | Vision model | Requires understanding |
| Bulk processing | PaddleOCR | Free, no API costs |

---

## Revised Plan (2026-01-16)

### Decision gates (blocking)
1. **OCR engine compatibility with Python 3.13**  
   - If PaddleOCR does **not** support 3.13: run OCR in a sidecar container (Python 3.10/3.11), or switch to Tesseract/RapidOCR.
2. **Scope**  
   - Decide whether v1 supports **images only** or **images + PDFs** (PDF support adds conversion dependencies).

### Implementation steps (lean)
1. **Security + file sandbox**  
   - OCR tools must use `FileSandbox` validation, not raw paths.  
   - Extend allowed extensions to include images (`.png`, `.jpg`, `.jpeg`, `.webp`, `.tiff`) and (optionally) `.pdf`.
2. **Local OCR tool (PaddleOCR/Tesseract)**  
   - Lazy-initialize engine in `src/cassey/tools/ocr_tool.py`.  
   - Read files via validated sandbox path (binary read for images).
3. **Method selection fix**  
   - `choose_ocr_method()` returns `local` or `vision`, aligned with `extract_from_image()`.
4. **Structured OCR**  
   - `ocr_extract_structured()` runs local OCR, then LLM formatting with JSON-only output and validation (bounded retry).
5. **PDF handling (if enabled)**  
   - Convert PDF pages to images (cap pages, e.g., first 3 by default).  
   - Provide args: `pages="1,2"` or `max_pages=3`.
6. **Vision fallback**  
   - Only available if vision API key configured; otherwise return a clear error.  
   - Keep as optional to avoid network dependence.
7. **Docs + config**  
   - Add `OCR_ENGINE`, `OCR_LANG`, `OCR_USE_GPU`, `OCR_MAX_PAGES`, `OCR_MAX_SIZE_MB`.  
   - Update `README.md` and Dockerfile if local OCR is included.
8. **Tests**  
   - Unit tests for method selection, sandbox validation, and error paths.  
   - Integration tests can be skipped by default.

### Feasibility / bloat
- **Lean if local-only** (no PDF + no vision): small surface area, low risk.  
- **Moderate if PDF + vision**: extra dependencies, more config, more tests.  
- **Heavy if sidecar**: extra service + deployment complexity.

---

## Implementation Checklist

- [ ] Add OCR dependencies to `pyproject.toml` (or a sidecar if PaddleOCR unsupported on 3.13)
- [ ] Update Dockerfile with system dependencies (if local OCR)
- [ ] Implement `ocr_tool.py` with PaddleOCR
- [ ] Add lazy initialization for OCR engine
- [ ] Implement auto-selection logic
- [ ] Add `extract_from_image` hybrid tool
- [ ] Add vision model fallback (optional)
- [ ] Add FileSandbox validation for OCR inputs
- [ ] Add image extensions to allowed file types
- [ ] Test with various image types
- [ ] Document OCR capabilities in README
- [ ] Add language selection (en/ch)

---

## Summary

| Decision | Choice |
|----------|--------|
| **Primary OCR** | PaddleOCR (local, free) |
| **Fallback** | GPT-4o Vision (structured data) |
| **Auto-selection** | Based on task complexity |
| **Default language** | English (configurable) |
| **Deployment** | Include in main Docker image |
| **Priority** | Medium (after core workflow features) |

**Key takeaway**: PaddleOCR is an excellent choice for Cassey - lightweight, fast, free, and great Chinese/English support. Add it as the default OCR tool, with vision model available for complex structured extraction tasks.
