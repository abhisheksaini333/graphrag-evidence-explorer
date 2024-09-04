"""Conservative syntactic support checks for model-extracted relationships.

These checks reject unsupported names and misassigned clauses. They do not
establish semantic entailment: source assertions may themselves be false.
"""
import json
import re
from .domain import Invalid


FIELDS = ('subject','relation','object')


def parse_triples(raw, source):
    if not isinstance(raw,str) or len(raw) > 20000:
        raise Invalid("Extraction output exceeds its schema limit")
    try:
        rows = json.loads(raw)
    except ValueError as exc:
        raise Invalid("Extraction did not return a JSON array") from exc
    if not isinstance(rows,list) or len(rows) > 32:
        raise Invalid("Extraction must contain at most 32 relationship objects")
    accepted, rejected, seen = [], [], set()
    clauses = list(re.finditer(r'[^.!?\n]+(?:[.!?]|$)',source))
    for row in rows:
        if not isinstance(row,dict) or set(row) != set(FIELDS) or any(not isinstance(row[key],str) for key in FIELDS):
            raise Invalid("Relationships require exactly three string fields: subject, relation, object")
        values = {key:row[key].strip() for key in FIELDS}
        if any(not value or len(value) > 100 or any(mark in value for mark in ('<','>','#','"','\n','\x00')) for value in values.values()):
            rejected.append({'triple':values,'reason':'invalid_label'})
            continue
        identity = tuple(values[key].casefold() for key in FIELDS)
        if identity in seen:
            continue
        seen.add(identity)
        pattern = r'(?<!\w)' + r'.*?'.join(re.escape(values[key]) + r'(?!\w)' for key in FIELDS)
        support = next((clause for clause in clauses if re.search(pattern,clause.group(),re.IGNORECASE)),None)
        if support is None:
            rejected.append({'triple':values,'reason':'no_matching_source_clause'})
            continue
        if re.search(r"\b(no|not|never|cannot|without|may|might|could|if|unless)\b|n't\b",support.group(),re.IGNORECASE):
            rejected.append({'triple':values,'reason':'nonaffirmative_source_clause'})
            continue
        accepted.append({**values,'start':support.start(),'end':support.end(),'support':support.group()})
    return {'accepted':accepted,'rejected':rejected}
