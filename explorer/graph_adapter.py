"""GraphRAG0.1.1 extraction with a bounded structured local-model adapter."""
import asyncio
from .domain import Invalid
from .triples import parse_triples


EXTRACTION_PROMPT = (
    'Extract relationships from this text as JSON, with keys subject, relation, object. '
    'Use the exact entity names and relation words in the text. '
    'Text: {input_text} Return only a JSON array.'
)
PROFILE = 'graphrag-0.1.1:qwen2-c291d6fc:minilm-7dbbc903:triples-v1'


def graph_records(accepted):
    records,seen = [],set()
    for claim in accepted:
        for name in (claim['subject'],claim['object']):
            identity = name.casefold()
            if identity not in seen:
                records.append('("entity"<|>'+name+'<|>ENTITY<|>'+name+')')
                seen.add(identity)
        description = ' '.join(claim[key] for key in ('subject','relation','object'))
        records.append('("relationship"<|>'+claim['subject']+'<|>'+claim['object']+'<|>'+description+'<|>1)')
    return '##'.join(records)


async def extract_graph(source,invoke):
    """Invoke the actual framework extractor; invoke returns a real or test model result."""
    from graphrag.index.graph.extractors.graph.graph_extractor import GraphExtractor
    from graphrag.llm.types.llm_io import LLMOutput
    captured,errors = [],[]

    async def completion(prompt,**kwargs):
        rendered = prompt.format(**kwargs['variables'])
        response = await asyncio.to_thread(invoke,rendered)
        parsed = parse_triples(response['text'],source)
        captured.append({'response':response,**parsed})
        return LLMOutput(output=graph_records(parsed['accepted']))

    extractor = GraphExtractor(completion,prompt=EXTRACTION_PROMPT,max_gleanings=0,
                               on_error=lambda error,*args:errors.append(error))
    result = await extractor([source],{'entity_types':['entity']})
    if errors:
        raise errors[0]
    if not captured:
        raise Invalid('Model extraction failed validation; no graph result was published')
    graph = result.output
    return {**captured[0],
            'nodes':{str(name):dict(attrs) for name,attrs in graph.nodes(data=True)},
            'edges':[{'source':str(a),'target':str(b),**dict(attrs)} for a,b,attrs in graph.edges(data=True)],
            'framework':'graphrag-0.1.1'}
