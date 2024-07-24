"""Transactional SQLite corpus; immutable revisions and optimistic edits."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time
from .domain import Invalid, identifier


class Conflict(Invalid):
    pass


class Missing(Invalid):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
INSERT OR IGNORE INTO metadata VALUES ('generation',0);
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, revision INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0,
 updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
 document_id TEXT NOT NULL REFERENCES documents(id), revision INTEGER NOT NULL,
 title TEXT NOT NULL, text TEXT NOT NULL, content_hash TEXT NOT NULL,
 PRIMARY KEY (document_id,revision)
);
"""


class Store:
    def __init__(self, path, clock=time.time):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def generation(self):
        with self.connect() as db:
            return db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()[0]

    @staticmethod
    def _bump_generation(db):
        db.execute("UPDATE metadata SET value=value+1 WHERE key='generation'")

    def put_document(self, document, expected_revision=None):
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 0):
            raise Invalid("Expected revision must be a nonnegative integer")
        with self.transaction() as db:
            old = db.execute("SELECT * FROM documents WHERE id=?", (document.id,)).fetchone()
            if old and old['revision'] != expected_revision:
                raise Conflict("Document changed; reload its current revision")
            if not old and expected_revision not in (None,0):
                raise Conflict("Document does not have the expected revision")
            if old and not old['deleted']:
                previous = db.execute("SELECT * FROM revisions WHERE document_id=? AND revision=?", (document.id,old['revision'])).fetchone()
                if previous['title'] == document.title and previous['text'] == document.text:
                    return {'id':document.id,'revision':old['revision'],'changed':False}
            revision = old['revision'] + 1 if old else 1
            db.execute("INSERT INTO documents VALUES (?,?,0,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,deleted=0,updated_at=excluded.updated_at", (document.id,revision,self.clock()))
            db.execute("INSERT INTO revisions VALUES (?,?,?,?,?)", (document.id,revision,document.title,document.text,document.content_hash))
            self._bump_generation(db)
            return {'id':document.id,'revision':revision,'changed':True}

    def get_document(self, document_id, revision=None):
        identifier(document_id)
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE id=? AND deleted=0", (document_id,)).fetchone()
            if not row:
                raise Missing("Document is unavailable")
            result = db.execute("SELECT r.*,d.updated_at FROM revisions r JOIN documents d ON d.id=r.document_id WHERE r.document_id=? AND r.revision=?", (document_id,revision or row['revision'])).fetchone()
            if not result:
                raise Missing("Source revision is unavailable")
            return dict(result)

    def list_documents(self):
        with self.connect() as db:
            rows = db.execute("SELECT d.id,d.revision,d.updated_at,r.title,r.content_hash,length(r.text) AS characters FROM documents d JOIN revisions r ON r.document_id=d.id AND r.revision=d.revision WHERE d.deleted=0 ORDER BY d.id")
            return [dict(row) for row in rows]
