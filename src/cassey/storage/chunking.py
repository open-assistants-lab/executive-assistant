"""Document chunking utilities for VS ingestion.

Chunks documents by paragraph, page, or fixed size while preserving metadata.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any


@dataclass
class Chunk:
    """A chunk of document content with metadata."""

    content: str
    metadata: dict = field(default_factory=dict)


# =============================================================================
# Embedding Model Cache
# =============================================================================

@lru_cache(maxsize=1)
def _get_embedding_model():
    """Get the sentence-transformers model (cached)."""
    from sentence_transformers import SentenceTransformer
    from cassey.config import settings
    return SentenceTransformer(settings.VS_EMBEDDING_MODEL)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Args:
        texts: List of text strings.

    Returns:
        List of embedding vectors (384 dimensions each).
    """
    model = _get_embedding_model()
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
    return embeddings.tolist()


def get_embedding(text: str) -> list[float]:
    """Generate embedding for a single text.

    Args:
        text: Text string.

    Returns:
        Embedding vector (384 dimensions).
    """
    return get_embeddings([text])[0]


# =============================================================================
# Chunking Functions
# =============================================================================

def _generate_document_id() -> str:
    """Generate a unique document ID."""
    return f"doc_{uuid.uuid4().hex[:16]}"


def chunk_by_paragraph(
    content: str,
    filename: str,
    chunk_size_chars: int = 3000,
    **extra_meta: Any,
) -> list[Chunk]:
    """Chunk content by paragraph (blank line separator).

    Args:
        content: Document content.
        filename: Source filename.
        chunk_size_chars: Maximum chunk size before forced split.
        **extra_meta: Additional metadata to include.

    Returns:
        List of chunks with metadata.
    """
    if not content.strip():
        return []

    # Split by blank lines (paragraphs)
    paragraphs = re.split(r'\n\s*\n', content)

    chunks = []
    current_chunk = ""
    chunk_idx = 0
    document_id = _generate_document_id()

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph would exceed chunk size and we have content
        if len(current_chunk) + len(para) > chunk_size_chars and current_chunk:
            chunks.append(Chunk(
                content=current_chunk.strip(),
                metadata={
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_index": chunk_idx,
                    "chunk_type": "paragraph",
                    **extra_meta
                }
            ))
            chunk_idx += 1
            current_chunk = para
        else:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para

    # Add remaining content
    if current_chunk.strip():
        chunks.append(Chunk(
            content=current_chunk.strip(),
            metadata={
                "document_id": document_id,
                "filename": filename,
                "chunk_index": chunk_idx,
                "chunk_type": "paragraph",
                **extra_meta
            }
        ))

    return chunks


def chunk_by_size(
    content: str,
    filename: str,
    chunk_size: int = 3000,
    **extra_meta: Any,
) -> list[Chunk]:
    """Chunk content by fixed character size.

    Args:
        content: Document content.
        filename: Source filename.
        chunk_size: Maximum characters per chunk.
        **extra_meta: Additional metadata to include.

    Returns:
        List of chunks with metadata.
    """
    if not content.strip():
        return []

    chunks = []
    document_id = _generate_document_id()
    chunk_idx = 0

    for i in range(0, len(content), chunk_size):
        chunk_content = content[i:i + chunk_size].strip()
        if chunk_content:
            chunks.append(Chunk(
                content=chunk_content,
                metadata={
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_index": chunk_idx,
                    "chunk_type": "fixed_size",
                    **extra_meta
                }
            ))
            chunk_idx += 1

    return chunks


def chunk_pdf_by_page(
    content: str,
    filename: str,
    chunk_size_chars: int = 3000,
    **extra_meta: Any,
) -> list[Chunk]:
    """Chunk PDF content by page markers.

    This looks for page markers like "--- Page N ---" or similar patterns.

    Args:
        content: Document content (extracted from PDF).
        filename: Source filename.
        chunk_size_chars: Maximum chunk size before forced split.
        **extra_meta: Additional metadata to include.

    Returns:
        List of chunks with metadata.
    """
    if not content.strip():
        return []

    # Try to detect page breaks
    page_pattern = r'(?:---+\s*Page\s*(\d+)\s*---+|\\f|\x0C)'

    # If page markers found, split by them
    if re.search(page_pattern, content, re.IGNORECASE):
        parts = re.split(page_pattern, content, flags=re.IGNORECASE)

        chunks = []
        current_page = 1
        document_id = _generate_document_id()

        for i in range(0, len(parts), 2):
            page_content = parts[i].strip() if i < len(parts) else ""
            page_num = parts[i + 1] if i + 1 < len(parts) else str(current_page)

            if page_content:
                # Further split by paragraphs if too long
                sub_chunks = chunk_by_paragraph(
                    page_content,
                    filename,
                    chunk_size_chars,
                    page_num=page_num,
                    **extra_meta
                )

                for sub in sub_chunks:
                    sub.metadata["document_id"] = document_id
                    sub.metadata["chunk_type"] = "pdf_page"
                    chunks.append(sub)

                current_page = page_num

        return chunks

    # No page markers found, fall back to paragraph chunking
    return chunk_by_paragraph(content, filename, chunk_size_chars, **extra_meta)


def chunk_from_file(
    file_path: str,
    content: str,
    file_type: str = "txt",
    **extra_meta: Any,
) -> list[Chunk]:
    """Chunk content from a file, auto-detecting strategy by file type.

    Args:
        file_path: Path to the file.
        content: File content.
        file_type: File type extension (pdf, txt, md, docx, etc.)
        **extra_meta: Additional metadata to include.

    Returns:
        List of chunks with metadata.
    """
    filename = file_path.split("/")[-1] if "/" in file_path else file_path
    file_type = file_type.lower().lstrip(".")

    chunking_map = {
        "pdf": chunk_pdf_by_page,
        "txt": chunk_by_paragraph,
        "text": chunk_by_paragraph,
        "md": chunk_by_paragraph,
        "markdown": chunk_by_paragraph,
    }

    chunker = chunking_map.get(file_type, chunk_by_size)

    return chunker(
        content=content,
        filename=filename,
        **extra_meta
    )


# =============================================================================
# Document Processing for VS
# =============================================================================

def prepare_documents_for_vs(
    documents: list[dict[str, Any]],
    auto_chunk: bool = True,
) -> list[Chunk]:
    """Prepare documents for VS ingestion with optional auto-chunking.

    Args:
        documents: List of document dicts with 'content' and optional 'metadata'.
        auto_chunk: If True, auto-chunk long documents.

    Returns:
        List of chunks ready for embedding and storage.
    """
    all_chunks = []

    for doc in documents:
        content = doc.get("content", "")
        metadata = doc.get("metadata", {})

        if not isinstance(metadata, dict):
            metadata = {"original_metadata": metadata}

        if not auto_chunk or len(content) <= 3000:
            # No chunking needed
            all_chunks.append(Chunk(
                content=content,
                metadata={
                    "document_id": _generate_document_id(),
                    "filename": metadata.get("filename", "unknown"),
                    "chunk_index": 0,
                    "chunk_type": "document",
                    **metadata
                }
            ))
        else:
            # Auto-chunk by paragraph
            filename = metadata.get("filename", "unknown")
            chunks = chunk_by_paragraph(
                content=content,
                filename=filename,
                **{k: v for k, v in metadata.items() if k != "filename"}
            )
            all_chunks.extend(chunks)

    return all_chunks
