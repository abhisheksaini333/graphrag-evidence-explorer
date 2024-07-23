import unittest
from explorer.chunking import chunk_document
from explorer.domain import Invalid


class ChunkingTests(unittest.TestCase):
    def test_spans_cover_original_with_bounded_overlap(self):
        text = 'Café owns Atlas.\n' * 80
        rows = chunk_document('atlas', 2, text, size=120, overlap=25)
        self.assertGreater(len(rows), 3)
        self.assertEqual(rows[0].start, 0)
        self.assertEqual(rows[-1].end, len(text))
        for row in rows:
            self.assertEqual(row.text, text[row.start:row.end])
            self.assertLessEqual(len(row.text),120)
        for a,b in zip(rows,rows[1:]):
            self.assertGreater(b.start,a.start)
            self.assertLessEqual(b.start,a.end)
        self.assertEqual(rows,chunk_document('atlas',2,text,size=120,overlap=25))
        self.assertNotEqual(rows[0].id,chunk_document('atlas',3,text,size=120,overlap=25)[0].id)

    def test_invalid_windows_cannot_loop(self):
        for size,overlap in [(0,0),(40,50),(64,-1),(True,0),(4096,0)]:
            with self.assertRaises(Invalid):chunk_document('atlas',1,'hello',size,overlap)
