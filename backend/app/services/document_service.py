"""Document text extraction and chunking service."""

import os
from pypdf import PdfReader
from docx import Document as DocxDocument


def extract_text_from_file(file_path: str, file_type: str) -> str:
    """Extract text content from a file based on its type."""
    file_type = file_type.lower()

    if file_type == "pdf":
        return _extract_pdf(file_path)
    elif file_type == "docx":
        return _extract_docx(file_path)
    elif file_type == "txt":
        return _extract_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def _extract_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    reader = PdfReader(file_path)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_docx(file_path: str) -> str:
    """Extract text from a DOCX file."""
    doc = DocxDocument(file_path)
    return "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())


def _extract_txt(file_path: str) -> str:
    """Extract text from a TXT file."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def split_text_into_chunks(text: str, chunk_size: int = 200, chunk_overlap: int = 40) -> list[str]:
    """Split text into overlapping word-based chunks.

    Args:
        text: The full text to split.
        chunk_size: Target number of words per chunk.
        chunk_overlap: Number of overlapping words between consecutive chunks.

    Returns:
        A list of text chunks.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - chunk_overlap
        if start >= len(words):
            break

    return chunks
