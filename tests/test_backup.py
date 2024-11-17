import sqlite3, tempfile, unittest
from pathlib import Path
from explorer.backup import backup
from explorer.domain import DocumentInput
from explorer.store import Store


class BackupTests(unittest.TestCase):
    def test_snapshot_contains_wal_data_and_preserves_existing_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            destination = Path(directory) / "copy"
            store = Store(source)
            store.put_document(DocumentInput("atlas", "Atlas", "Mira owns Atlas."))
            result = backup(source, destination)
            self.assertEqual(result["integrity"], "ok")
            self.assertEqual(
                Store(destination).get_document("atlas")["text"], "Mira owns Atlas."
            )
            before = destination.read_bytes()
            with self.assertRaises(FileExistsError):
                backup(source, destination)
            self.assertEqual(destination.read_bytes(), before)

    def test_missing_source_does_not_create_an_empty_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "missing"
            destination = Path(directory) / "copy"
            with self.assertRaises(ValueError):
                backup(source, destination)
            self.assertFalse(destination.exists())
