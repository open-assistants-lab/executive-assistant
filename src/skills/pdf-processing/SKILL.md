---
name: pdf-processing
description: Extract text and tables from PDF files, fill forms, merge documents. Use when user asks to work with PDF files, extract content from PDFs, or create PDF documents.
---

# PDF Processing Skill

## Overview

This skill provides guidance for working with PDF files using Python.

## Common Operations

### Extract Text from PDF

```python
import pdfplumber

def extract_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages)
    return text
```

### Extract Tables from PDF

```python
import pdfplumber

def extract_tables(pdf_path: str) -> list[list[list[str]]]:
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            tables.extend(page_tables)
    return tables
```

### Fill PDF Form

```python
import pypdf

def fill_form(pdf_path: str, field_values: dict) -> bytes:
    reader = pypdf.PdfReader(pdf_path)
    writer = pypdf.PdfWriter()
    
    writer.clone_reader_document_root(reader)
    
    for page in writer.pages:
        for field in page.get_fields().values():
            if field.get("/T") in field_values:
                field.set_value(field_values[field.get("/T")])
    
    return writer.write()
```

### Merge PDFs

```python
import pypdf

def merge_pdfs(pdf_paths: list[str], output_path: str) -> None:
    merger = pypdf.PdfMerger()
    for path in pdf_paths:
        merger.append(path)
    merger.write(output_path)
    merger.close()
```

### Create PDF from HTML

```python
from weasyprint import HTML

def html_to_pdf(html_content: str, output_path: str) -> None:
    HTML(string=html_content).write_pdf(output_path)
```

## Best Practices

1. **Text Extraction**: Use pdfplumber for better accuracy with complex layouts
2. **Tables**: Check table extraction and clean up None values
3. **Forms**: Verify field names using pdfplumber first
4. **Memory**: Process large PDFs page by page to avoid memory issues

## Dependencies

- `pdfplumber` - Text and table extraction
- `pypdf` - PDF manipulation and form filling
- `weasyprint` - HTML to PDF conversion
- `PyMuPDF` (fitz) - Low-level PDF operations

## Use Cases

- Extract invoice data from PDF receipts
- Fill out PDF forms programmatically
- Merge multiple PDF documents
- Convert HTML reports to PDF
- Extract table data from financial reports
