"""Durable bounded query costs and generation-fenced answer publication."""
import json,uuid
from .domain import Invalid,bounded_text
from .store import Conflict,Missing

class QueryBudgetExceeded(Invalid):pass

SCHEMA="""
CREATE TABLE IF NOT EXISTS query_runs (
 id TEXT PRIMARY KEY, mode TEXT NOT NULL, question TEXT NOT NULL,
 generation INTEGER NOT NULL, status TEXT NOT NULL, max_calls INTEGER NOT NULL,
 max_tokens INTEGER NOT NULL, created_at REAL NOT NULL, result TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS query_calls (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES query_runs(id),
 kind TEXT NOT NULL, reserved_tokens INTEGER NOT NULL, status TEXT NOT NULL,
 response TEXT, created_at REAL NOT NULL
);
"""

class QueryRuns:
    def __init__(self,store):
        self.store=store
        with store.connect() as db:db.executescript(SCHEMA)

    def start(self,mode,question,generation,max_calls=8,max_tokens=24000):
        if mode not in ('vector','local','global','community'):raise Invalid('Choose vector, local or global search')
        bounded_text(question,'Question',500)
        if type(max_calls) is not int or not 1<=max_calls<=8 or type(max_tokens) is not int or not 1<=max_tokens<=24000:raise Invalid('Query budget exceeds its hard limit')
        run_id=uuid.uuid4().hex
        with self.store.transaction() as db:
            if generation!=db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()[0]:raise Conflict('Corpus changed before query started')
            db.execute('INSERT INTO query_runs VALUES (?,?,?,?,?,?,?,?,NULL,NULL)',(run_id,mode,question,generation,'running',max_calls,max_tokens,self.store.clock()))
        return self.get(run_id)

    def reserve(self,run_id,kind,tokens):
        if type(tokens) is not int or tokens<1:raise Invalid('Token reservation must be positive')
        with self.store.transaction() as db:
            row=db.execute('SELECT * FROM query_runs WHERE id=?',(run_id,)).fetchone()
            if not row or row['status']!='running':raise Conflict('Query is no longer running')
            generation=db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()[0]
            if generation!=row['generation']:raise Conflict('Corpus changed during query')
            count,total=db.execute('SELECT COUNT(*),COALESCE(SUM(reserved_tokens),0) FROM query_calls WHERE run_id=?',(run_id,)).fetchone()
            if count>=row['max_calls'] or total+tokens>row['max_tokens']:raise QueryBudgetExceeded('Query exhausted its bounded model budget')
            call_id=uuid.uuid4().hex
            db.execute('INSERT INTO query_calls VALUES (?,?,?,?,?,NULL,?)',(call_id,run_id,kind,tokens,'pending',self.store.clock()))
            return call_id

    def complete_call(self,call_id,response):
        raw=json.dumps(response,allow_nan=False)
        if len(raw.encode())>200000:raise Invalid('Model response exceeds query trace limit')
        with self.store.transaction() as db:
            updated=db.execute("UPDATE query_calls SET status='complete',response=? WHERE id=? AND status='pending'",(raw,call_id)).rowcount
            if updated!=1:raise Conflict('Model call already completed or is unavailable')

    def finish(self,run_id,result,error=None):
        raw=json.dumps(result,allow_nan=False)
        with self.store.transaction() as db:
            row=db.execute('SELECT * FROM query_runs WHERE id=?',(run_id,)).fetchone()
            if not row or row['status']!='running':raise Conflict('Query already finalized')
            generation=db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()[0]
            status='stale' if generation!=row['generation'] else 'failed' if error else 'complete'
            db.execute('UPDATE query_runs SET status=?,result=?,error=? WHERE id=?',(status,raw if status=='complete' else None,error,run_id))
        return self.get(run_id)

    def get(self,run_id):
        with self.store.connect() as db:
            db.execute('BEGIN')
            row=db.execute('SELECT * FROM query_runs WHERE id=?',(run_id,)).fetchone()
            if not row:raise Missing('Query is unavailable')
            result=dict(row)
            current=db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()[0]
            result['result']=json.loads(row['result']) if row['result'] else None
            if current!=row['generation']:result['status']='stale';result['result']=None
            result['calls']=[{**dict(call),'response':json.loads(call['response']) if call['response'] else None} for call in db.execute('SELECT * FROM query_calls WHERE run_id=? ORDER BY created_at,id',(run_id,))]
            # Old model output can contain deleted/corrected source text. Hide it
            # from the live API as well as hiding its rendered answer.
            if current!=row['generation']:
                for call in result['calls']:call['response']=None
            return result

    def list(self):
        with self.store.connect() as db:
            ids=[row[0] for row in db.execute('SELECT id FROM query_runs ORDER BY created_at DESC LIMIT 30')]
        return [self.get(run_id) for run_id in ids]
