"""Reject ambiguous duplicate JSON members in model and operator contracts."""
import json
from .domain import Invalid

def strict_json(value):
    def unique(pairs):
        result={}
        for key,item in pairs:
            if key in result:raise Invalid('Duplicate JSON members are not accepted')
            result[key]=item
        return result
    try:return json.loads(value,object_pairs_hook=unique,parse_constant=lambda value:(_ for _ in ()).throw(Invalid('Nonfinite JSON values are not accepted')))
    except (TypeError,ValueError) as error:raise Invalid('Response is not an unambiguous JSON value') from error
