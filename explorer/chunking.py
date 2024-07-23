"""Deterministic character spans; stored offsets refer to unmodified source text."""
from dataclasses import dataclass
import hashlib
from .domain import Invalid, bounded_text, identifier


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    revision: int
    start: int
    end: int
    text: str


def chunk_document(document_id, revision, text, size=600, overlap=80):
    identifier(document_id)
    bounded_text(text, "Document text", 50000)
    if type(revision) is not int or revision < 1:
        raise Invalid("Revision must be a positive integer")
    if type(size) is not int or not 64 <= size <= 2048:
        raise Invalid("Chunk size must be between 64 and 2048 characters")
    if type(overlap) is not int or not 0 <= overlap < size // 2:
        raise Invalid("Overlap must be nonnegative and smaller than half a chunk")
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", start + size // 2, end),
                           text.rfind(" ", start + size // 2, end))
            if boundary > start:
                end = boundary + 1
        digest = hashlib.sha256(f"{document_id}:{revision}:{start}:{end}".encode()).hexdigest()[:32]
        chunks.append(Chunk(digest, document_id, revision, start, end, text[start:end]))
        if end == len(text):
            break
        start = end - overlap
    return chunks
