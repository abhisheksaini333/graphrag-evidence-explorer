"""Durable conservative model reservations, including interrupted requests."""
import json
import uuid
from .domain import Invalid, bounded_text
from .store import Conflict, Missing


class BudgetExceeded(Invalid):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS budgets (
 job_id TEXT PRIMARY KEY REFERENCES jobs(id), max_calls INTEGER NOT NULL,
 max_tokens INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS model_calls (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), call_key TEXT NOT NULL,
 lease_token TEXT NOT NULL, reserved_tokens INTEGER NOT NULL, status TEXT NOT NULL,
 result TEXT, actual_tokens INTEGER, created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS model_call_identity ON model_calls(job_id,call_key,status);
"""


def positive_int(value, maximum, label):
    if type(value) is not int or not 1 <= value <= maximum:
        raise Invalid(f"{label} must be between 1 and {maximum}")


class ModelBudget:
    def __init__(self, jobs):
        self.jobs, self.store = jobs, jobs.store
        with self.store.connect() as db:
            db.executescript(SCHEMA)

    def configure(self, job_id, max_calls=32, max_tokens=65536):
        positive_int(max_calls, 128, "Call budget")
        positive_int(max_tokens, 262144, "Token budget")
        with self.store.transaction() as db:
            if not db.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
                raise Missing("Index job is unavailable")
            old = db.execute(
                "SELECT * FROM budgets WHERE job_id=?", (job_id,)
            ).fetchone()
            if (
                old
                and old["max_calls"] == max_calls
                and old["max_tokens"] == max_tokens
            ):
                return
            if db.execute(
                "SELECT 1 FROM model_calls WHERE job_id=? LIMIT 1", (job_id,)
            ).fetchone():
                raise Conflict(
                    "An active usage budget is immutable; completed calls are retained"
                )
            db.execute(
                "INSERT INTO budgets VALUES (?,?,?) ON CONFLICT(job_id) DO UPDATE SET max_calls=excluded.max_calls,max_tokens=excluded.max_tokens",
                (job_id, max_calls, max_tokens),
            )

    def reserve(self, job_id, token, call_key, tokens):
        bounded_text(call_key, "Model call identity", 200)
        positive_int(tokens, 16384, "Request token reservation")
        with self.store.transaction() as db:
            self.jobs.require_owner(db, job_id, token)
            cached = db.execute(
                "SELECT * FROM model_calls WHERE job_id=? AND call_key=? AND status='complete' ORDER BY created_at,id LIMIT 1",
                (job_id, call_key),
            ).fetchone()
            if cached:
                return {"id": cached["id"], "cached": json.loads(cached["result"])}
            active = db.execute(
                "SELECT 1 FROM model_calls WHERE job_id=? AND call_key=? AND lease_token=? AND status='pending'",
                (job_id, call_key, token),
            ).fetchone()
            if active:
                raise Conflict("This worker already reserved the model call")
            limit = db.execute(
                "SELECT * FROM budgets WHERE job_id=?", (job_id,)
            ).fetchone()
            if not limit:
                raise Invalid("Configure a model budget before indexing")
            usage = db.execute(
                "SELECT count(*) AS calls,coalesce(sum(reserved_tokens),0) AS tokens FROM model_calls WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if (
                usage["calls"] >= limit["max_calls"]
                or usage["tokens"] + tokens > limit["max_tokens"]
            ):
                raise BudgetExceeded(
                    "Index model budget exhausted; completed extraction remains available"
                )
            call_id = uuid.uuid4().hex
            db.execute(
                "INSERT INTO model_calls(id,job_id,call_key,lease_token,reserved_tokens,status,created_at) VALUES (?,?,?,?,?,'pending',?)",
                (call_id, job_id, call_key, token, tokens, self.store.clock()),
            )
            return {"id": call_id, "cached": None}

    def complete(self, call_id, token, result, actual_tokens):
        if type(actual_tokens) is not int or actual_tokens < 0:
            raise Invalid("Actual usage must be a nonnegative integer")
        encoded = json.dumps(result, sort_keys=True, allow_nan=False)
        if len(encoded.encode()) > 100000:
            raise Invalid("Model result exceeds the retained output limit")
        with self.store.transaction() as db:
            row = db.execute(
                "SELECT * FROM model_calls WHERE id=? AND lease_token=? AND status='pending'",
                (call_id, token),
            ).fetchone()
            if not row:
                raise Conflict("Model reservation is no longer owned by this worker")
            self.jobs.require_owner(db, row["job_id"], token)
            if actual_tokens > row["reserved_tokens"]:
                raise Invalid("Model usage exceeded its reserved request bound")
            db.execute(
                "UPDATE model_calls SET status='complete',result=?,actual_tokens=? WHERE id=?",
                (encoded, actual_tokens, call_id),
            )

    def usage(self, job_id):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT count(*) AS calls,coalesce(sum(reserved_tokens),0) AS reserved_tokens,coalesce(sum(actual_tokens),0) AS actual_tokens,sum(CASE WHEN status='complete' THEN 1 ELSE 0 END) AS completed_calls FROM model_calls WHERE job_id=?",
                (job_id,),
            ).fetchone()
            limit = db.execute(
                "SELECT max_calls,max_tokens FROM budgets WHERE job_id=?", (job_id,)
            ).fetchone()
            return {**dict(row), **(dict(limit) if limit else {})}
