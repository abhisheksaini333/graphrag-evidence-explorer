"""Owned publication of framework extraction with live-source graph snapshots."""
import hashlib
import json
import math
from .domain import Invalid
from .store import Conflict


SCHEMA = """
CREATE TABLE IF NOT EXISTS extractions (
 job_id TEXT NOT NULL REFERENCES jobs(id), chunk_id TEXT NOT NULL REFERENCES chunks(id),
 result TEXT NOT NULL, vector TEXT NOT NULL, PRIMARY KEY(job_id,chunk_id)
);
CREATE TABLE IF NOT EXISTS claims (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
 chunk_id TEXT NOT NULL REFERENCES chunks(id), subject TEXT NOT NULL,
 relation TEXT NOT NULL, object TEXT NOT NULL, start INTEGER NOT NULL,
 end INTEGER NOT NULL, support TEXT NOT NULL
);
"""


def normalized_vector(value):
    if not isinstance(value,list) or len(value) != 384:
        raise Invalid("MiniLM embeddings must have 384 dimensions")
    if any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>1000000 for x in value):
        raise Invalid("Embedding must contain bounded finite numbers")
    norm = math.sqrt(sum(x*x for x in value))
    if norm < 1e-12:
        raise Invalid("Empty embeddings cannot be indexed")
    return [x/norm for x in value]


class EvidenceStore:
    def __init__(self,jobs):
        self.jobs,self.store = jobs,jobs.store
        with self.store.connect() as db:
            db.executescript(SCHEMA)

    def publish(self,job_id,token,chunk_id,result,vector):
        vector_json = json.dumps(normalized_vector(vector),allow_nan=False)
        result_json = json.dumps(result,sort_keys=True,allow_nan=False)
        if len(result_json.encode()) > 200000 or not isinstance(result.get('accepted'),list):
            raise Invalid("Extraction result exceeds the publication contract")
        with self.store.transaction() as db:
            job = self.jobs.require_owner(db,job_id,token)
            chunk = db.execute("SELECT * FROM chunks WHERE id=? AND document_id=? AND revision=?", (chunk_id,job['document_id'],job['revision'])).fetchone()
            if not chunk:
                raise Conflict("Passage does not belong to the owned source revision")
            existing = db.execute("SELECT * FROM extractions WHERE job_id=? AND chunk_id=?", (job_id,chunk_id)).fetchone()
            if existing:
                if existing['result'] != result_json or existing['vector'] != vector_json:
                    raise Conflict("Published passage extraction is immutable")
                return False
            edges = {frozenset((edge['source'],edge['target'])) for edge in result.get('edges',[])}
            for claim in result['accepted']:
                start,end = claim['start'],claim['end']
                if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(chunk['text']):
                    raise Invalid("Claim offsets must refer to the indexed passage")
                if chunk['text'][start:end] != claim['support']:
                    raise Invalid("Claim support does not equal its source span")
                endpoints = frozenset((claim['subject'].upper(),claim['object'].upper()))
                if endpoints not in edges:
                    raise Invalid("Claim was not represented in the framework graph")
                identity = json.dumps([job_id,chunk_id,*[claim[k].casefold() for k in ('subject','relation','object')]])
                claim_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
                db.execute("INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?)", (claim_id,job_id,chunk_id,claim['subject'],claim['relation'],claim['object'],start,end,claim['support']))
            db.execute("INSERT INTO extractions VALUES (?,?,?,?)", (job_id,chunk_id,result_json,vector_json))
            return True

    def completed_chunks(self,job_id):
        with self.store.connect() as db:
            return {row[0] for row in db.execute("SELECT chunk_id FROM extractions WHERE job_id=?", (job_id,))}

    def snapshot(self,profile):
        with self.store.connect() as db:
            db.execute('BEGIN')
            generation = db.execute("SELECT value FROM metadata WHERE key='generation'").fetchone()[0]
            claims = [dict(row) for row in db.execute("SELECT a.*,c.document_id,c.revision,c.start AS passage_start,r.title FROM claims a JOIN jobs j ON j.id=a.job_id JOIN chunks c ON c.id=a.chunk_id JOIN documents d ON d.id=c.document_id AND d.revision=c.revision JOIN revisions r ON r.document_id=c.document_id AND r.revision=c.revision WHERE j.status='complete' AND j.profile=? AND d.deleted=0 ORDER BY a.id", (profile,))]
            vectors = []
            for row in db.execute("SELECT e.chunk_id,e.vector,c.document_id,c.revision,c.start,c.end,c.text,r.title FROM extractions e JOIN jobs j ON j.id=e.job_id JOIN chunks c ON c.id=e.chunk_id JOIN documents d ON d.id=c.document_id AND d.revision=c.revision JOIN revisions r ON r.document_id=c.document_id AND r.revision=c.revision WHERE j.status='complete' AND j.profile=? AND d.deleted=0 ORDER BY c.document_id,c.start", (profile,)):
                item = dict(row)
                item['vector'] = json.loads(item['vector'])
                vectors.append(item)
            db.commit()
            return {'generation':generation,'claims':claims,'vectors':vectors}

    def extraction_details(self,job_id):
        with self.store.connect() as db:
            return [{'chunk_id':row['chunk_id'],'result':json.loads(row['result'])} for row in db.execute("SELECT chunk_id,result FROM extractions WHERE job_id=? ORDER BY chunk_id", (job_id,))]
