"""Exclusive, revision-bound indexing jobs with expiring ownership tokens."""
import hashlib
import uuid
from .domain import Invalid, bounded_text
from .store import Conflict, Missing


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL, revision INTEGER NOT NULL,
 profile TEXT NOT NULL, status TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
 worker TEXT, lease_token TEXT, lease_until REAL NOT NULL DEFAULT 0,
 created_at REAL NOT NULL, error TEXT,
 FOREIGN KEY(document_id,revision) REFERENCES revisions(document_id,revision)
);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status,created_at);
"""


def lease_duration(value):
    if type(value) not in (int,float) or not 1 <= value <= 300:
        raise Invalid("Lease must be between 1 and 300 seconds")
    return value


class JobQueue:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript(SCHEMA)

    def enqueue(self, document_id, profile):
        bounded_text(profile, "Index profile", 160)
        with self.store.transaction() as db:
            doc = db.execute("SELECT * FROM documents WHERE id=? AND deleted=0", (document_id,)).fetchone()
            if not doc:
                raise Missing("Document is unavailable")
            job_id = hashlib.sha256(f"{document_id}:{doc['revision']}:{profile}".encode()).hexdigest()[:32]
            db.execute("INSERT OR IGNORE INTO jobs(id,document_id,revision,profile,status,created_at) VALUES (?,?,?,?,?,?)", (job_id,document_id,doc['revision'],profile,'queued',self.store.clock()))
            return dict(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def get(self, job_id):
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise Missing("Index job is unavailable")
            return dict(row)

    def list(self):
        with self.store.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY created_at DESC,id LIMIT 200")]

    def claim(self, worker, lease_seconds=120):
        bounded_text(worker, "Worker", 100)
        lease_duration(lease_seconds)
        now = self.store.clock()
        with self.store.transaction() as db:
            db.execute("UPDATE jobs SET status='superseded',lease_token=NULL,lease_until=0,error='source_changed' WHERE status IN ('queued','running') AND NOT EXISTS (SELECT 1 FROM documents d WHERE d.id=jobs.document_id AND d.revision=jobs.revision AND d.deleted=0)")
            db.execute("UPDATE jobs SET status=CASE WHEN attempt>=3 THEN 'failed' ELSE 'queued' END,error=CASE WHEN attempt>=3 THEN 'lease_exhausted' ELSE 'worker_interrupted' END,lease_token=NULL,lease_until=0 WHERE status='running' AND lease_until<=?", (now,))
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if not row:
                return None
            token = uuid.uuid4().hex
            db.execute("UPDATE jobs SET status='running',attempt=attempt+1,worker=?,lease_token=?,lease_until=?,error=NULL WHERE id=?", (worker,token,now+lease_seconds,row['id']))
            return dict(db.execute("SELECT * FROM jobs WHERE id=?", (row['id'],)).fetchone())

    def require_owner(self, db, job_id, token):
        row = db.execute("SELECT j.* FROM jobs j JOIN documents d ON d.id=j.document_id AND d.revision=j.revision WHERE j.id=? AND j.status='running' AND j.lease_token=? AND j.lease_until>? AND d.deleted=0", (job_id,token,self.store.clock())).fetchone()
        if not row:
            raise Conflict("Index ownership expired, was cancelled, or its source changed")
        return dict(row)

    def heartbeat(self, job_id, token, lease_seconds=120):
        lease_duration(lease_seconds)
        with self.store.transaction() as db:
            self.require_owner(db,job_id,token)
            db.execute("UPDATE jobs SET lease_until=? WHERE id=?", (self.store.clock()+lease_seconds,job_id))

    def finish(self, job_id, token, status, error=None):
        if status not in ('complete','failed'):
            raise Invalid("Invalid job completion state")
        if error is not None:
            bounded_text(error,"Error code",80)
        with self.store.transaction() as db:
            self.require_owner(db,job_id,token)
            db.execute("UPDATE jobs SET status=?,error=?,lease_token=NULL,lease_until=0 WHERE id=?", (status,error,job_id))
            if status == "complete":
                self.store._bump_generation(db)

    def cancel(self, job_id):
        with self.store.transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise Missing("Index job is unavailable")
            if row['status'] not in ('queued','running','cancelled'):
                raise Conflict("Only pending indexing can be cancelled")
            db.execute("UPDATE jobs SET status='cancelled',lease_token=NULL,lease_until=0,error='operator_cancelled' WHERE id=?", (job_id,))
        return self.get(job_id)

    def retry(self, job_id):
        with self.store.transaction() as db:
            row = db.execute("SELECT j.* FROM jobs j JOIN documents d ON d.id=j.document_id AND d.revision=j.revision WHERE j.id=? AND d.deleted=0", (job_id,)).fetchone()
            if not row or row['status'] not in ('failed','cancelled') or row['attempt'] >= 3:
                raise Conflict("Retry requires a current failed/cancelled job with attempts remaining")
            db.execute("UPDATE jobs SET status='queued',error=NULL WHERE id=?", (job_id,))
        return self.get(job_id)
