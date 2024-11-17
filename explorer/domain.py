"""Small validated contracts shared by storage, workers and HTTP handlers."""
from dataclasses import dataclass
import hashlib
import re


class Invalid(ValueError):
    """A request cannot safely be accepted."""


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", value
    ):
        raise Invalid(
            "Use an identifier of 1–80 letters, digits, underscores or hyphens"
        )
    return value


def bounded_text(value, name, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise Invalid(f"{name} must contain 1–{maximum} characters")
    if "\x00" in value:
        raise Invalid(f"{name} cannot contain NUL characters")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise Invalid(f"{name} must be valid UTF-8") from exc
    return value


@dataclass(frozen=True)
class DocumentInput:
    id: str
    title: str
    text: str

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict):
            raise Invalid("Document must be an object")
        return cls(
            identifier(value.get("id")),
            bounded_text(value.get("title"), "Title", 160),
            bounded_text(value.get("text"), "Document text", 50000),
        )

    @property
    def content_hash(self):
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()
