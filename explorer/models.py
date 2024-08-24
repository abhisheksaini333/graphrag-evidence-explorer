"""Local model artifact and request contracts without framework imports."""
import hashlib
import json
from pathlib import Path
from .domain import Invalid,bounded_text


MANIFEST = Path(__file__).resolve().parents[1]/'dependencies/models.json'


def model_manifest():
    return json.loads(MANIFEST.read_text())


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def verify_model(directory, specification):
    root = Path(directory)
    for item in specification['files']:
        filename = item['file']
        if Path(filename).name != filename:
            raise Invalid("Model manifest must contain simple file names")
        path = root/filename
        if not path.is_file() or sha256_file(path) != item['sha256']:
            raise Invalid("Missing or changed model artifact: " + filename)
    return root


def generation_request(value):
    if not isinstance(value,dict) or set(value)-{'prompt','max_new_tokens'}:
        raise Invalid("Generation accepts prompt and max_new_tokens only")
    prompt = bounded_text(value.get('prompt'),'Model prompt',12000)
    tokens = value.get('max_new_tokens',192)
    if type(tokens) is not int or not 1 <= tokens <= 256:
        raise Invalid("Generation output must be bounded to 1–256 tokens")
    return prompt,tokens


def embedding_request(value):
    if not isinstance(value,dict) or set(value) != {'texts'}:
        raise Invalid("Embedding accepts a texts array")
    texts = value['texts']
    if not isinstance(texts,list) or not 1 <= len(texts) <= 32:
        raise Invalid("Embedding batches contain 1–32 texts")
    for text in texts:
        bounded_text(text,'Embedding text',16000)
    if sum(len(text) for text in texts) > 16000:
        raise Invalid("Embedding batch exceeds 16000 characters")
    return texts
