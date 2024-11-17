import unittest
from explorer.domain import DocumentInput, Invalid


class DocumentInputTests(unittest.TestCase):
    def test_identity_depends_on_exact_utf8_body(self):
        a = DocumentInput.parse(
            {"id": "atlas", "title": "Atlas guide", "text": "Mira owns Atlas.\n"}
        )
        b = DocumentInput.parse(
            {"id": "atlas", "title": "Renamed", "text": "Mira owns Atlas.\n"}
        )
        self.assertEqual(a.content_hash, b.content_hash)
        self.assertNotEqual(
            a.content_hash,
            DocumentInput.parse(
                {"id": "atlas", "title": "Atlas", "text": "Mira owns Atlas."}
            ).content_hash,
        )

    def test_rejects_unbounded_or_ambiguous_payloads(self):
        base = {"id": "atlas", "title": "Atlas", "text": "Mira owns Atlas."}
        for key, value in [
            ("id", "../x"),
            ("id", ""),
            ("title", " "),
            ("text", ""),
            ("text", "x" * 50001),
            ("text", "bad\x00text"),
            ("text", 42),
        ]:
            with self.subTest(key=key, value=str(value)[:30]), self.assertRaises(
                Invalid
            ):
                DocumentInput.parse({**base, key: value})

    def test_retains_unicode_and_offsets_without_normalization(self):
        text = "Mira owns Café.\r\nNora owns Cedar."
        self.assertEqual(
            DocumentInput.parse({"id": "guide", "title": "Guide", "text": text}).text,
            text,
        )
