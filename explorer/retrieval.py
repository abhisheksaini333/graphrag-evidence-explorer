"""Bounded vector and graph retrieval with explicit source-citation validation."""
import json,re
from .domain import Invalid
from .json_contract import strict_json
from .evidence import normalized_vector


def retrieve(snapshot,question,mode,query_vector,limit=6,character_budget=2400,graph=None):
    if mode not in ('vector','local','global'):raise Invalid('Unknown retrieval mode')
    query_vector=normalized_vector(query_vector)
    ranked=sorted(snapshot['vectors'],key=lambda p:(-sum(a*b for a,b in zip(query_vector,p['vector'])),p['chunk_id']))
    selected=[]
    if mode=='local':
        labels={c[k].casefold() for c in snapshot['claims'] for k in ('subject','object')}
        frontier={label for label in labels if re.search(r'(?<!\w)'+re.escape(label)+r'(?!\w)',question.casefold())}
        for _ in range(2):
            matching=[c for c in snapshot['claims'] if c['subject'].casefold() in frontier or c['object'].casefold() in frontier]
            ids={c['chunk_id'] for c in matching}
            selected.extend(p for p in ranked if p['chunk_id'] in ids and p not in selected)
            frontier|={c[k].casefold() for c in matching for k in ('subject','object')}
    elif mode=='global' and graph:
        rank={p['chunk_id']:i for i,p in enumerate(ranked)}
        claim_chunks={c['id']:c['chunk_id'] for c in snapshot['claims']}
        groups=[{claim_chunks[c] for c in community['claim_ids']} for community in graph['communities']]
        groups.sort(key=lambda ids:min((rank.get(i,999999) for i in ids),default=999999))
        queues=[[p for p in ranked if p['chunk_id'] in group] for group in groups]
        while any(queues):
            for queue in queues:
                if queue:
                    passage=queue.pop(0)
                    if passage not in selected:selected.append(passage)
    selected.extend(p for p in ranked if p not in selected)
    passages=[];lines=[]
    for passage in selected:
        if len(passages)>=limit:break
        citation='S'+str(len(passages)+1)
        text=f'[{citation}] {passage["title"]}: {passage["text"]}'
        if len('\n'.join([*lines,text]))>character_budget:continue
        lines.append(text)
        passages.append({k:v for k,v in {**passage,'citation':citation,'score':sum(a*b for a,b in zip(query_vector,passage['vector']))}.items() if k!='vector'})
    return {'generation':snapshot['generation'],'passages':passages,'context':'\n'.join(lines)}


def check_answer(raw,allowed):
    try:value=strict_json(raw)
    except (TypeError,ValueError) as exc:raise Invalid('Model answer did not satisfy the JSON contract') from exc
    if not isinstance(value,dict) or set(value)!={'answer','citations'} or not isinstance(value['answer'],str) or not isinstance(value['citations'],list):raise Invalid('Answer requires text and a citation array')
    if len(value['answer'])>2000 or any(not isinstance(c,str) for c in value['citations']):raise Invalid('Answer exceeds citation contract')
    abstained=value['answer'].strip()=='Insufficient evidence.'
    cited=set(value['citations']);inline=set(re.findall(r'\[(S\d+)\]',value['answer']))
    if not cited<=set(allowed) or not inline<=cited or (not abstained and not cited) or (abstained and cited):raise Invalid('Answer citations are missing or outside the retrieved evidence')
    return {**value,'abstained':abstained,'verification':'citation_links_only'}
