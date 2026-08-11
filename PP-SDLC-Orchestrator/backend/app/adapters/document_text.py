"""Extracts readable text from a generated artefact file, so a downstream
LLM adapter can pass an upstream agent's actual output as prompt context
instead of just re-sending the original task request at every phase.
"""

from pathlib import Path

from docx import Document


def extract_text(file_path: Path, *, max_chars: int = 8000) -> str:
    """Best-effort plain-text extraction. Word docs are read paragraph by
    paragraph (the common case so far); anything else falls back to a raw
    read, truncated so upstream context can't blow out a prompt budget.
    """
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        doc = Document(str(file_path))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    else:
        text = file_path.read_text(encoding="utf-8", errors="replace")

    return text[:max_chars]
