"""Append-only operator decisions with optimistic graph-generation checks."""
from .domain import Invalid,bounded_text
from .store import Conflict

SCHEMA = """
CREATE TABLE IF NOT EXISTS corrections (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 claim_id TEXT NOT NULL REFERENCES claims(id), status TEXT NOT NULL,
 reason TEXT NOT NULL, created_at REAL NOT NULL, generation INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS correction_claim ON corrections(claim_id,sequence DESC);
"""

class Corrections:
    def __init__(self,evidence):
        self.evidence,self.store=evidence,evidence.store
        with self.store.connect() as db:db.executescript(SCHEMA)

    def set_status(self,claim_id,status,reason,expected_generation):
        if status not in ('accepted','rejected'):raise Invalid('Choose accepted or rejected')
        bounded_text(reason,'Correction reason',500)
        if type(expected_generation) is not int:raise Invalid('Current graph generation is required')
        with self.store.transaction() as db:
            generation=db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()[0]
            if generation!=expected_generation:raise Conflict('Graph changed; reload before correcting')
            claim=db.execute("SELECT a.id FROM claims a JOIN jobs j ON j.id=a.job_id JOIN chunks c ON c.id=a.chunk_id JOIN documents d ON d.id=c.document_id AND d.revision=c.revision WHERE a.id=? AND j.status='complete' AND d.deleted=0",(claim_id,)).fetchone()
            if not claim:raise Conflict('Claim source changed or is unavailable')
            self.store._bump_generation(db)
            db.execute('INSERT INTO corrections(claim_id,status,reason,created_at,generation) VALUES (?,?,?,?,?)',(claim_id,status,reason,self.store.clock(),generation+1))
        return {'claim_id':claim_id,'status':status,'generation':generation+1}

    def history(self):
        with self.store.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM corrections ORDER BY sequence DESC LIMIT 200')]
