# GraphRAG Evidence Explorer

Explore the passages behind a relationship, correct extracted evidence and compare vector, local graph and global community retrieval on the same collection.

The workspace includes versioned documents, durable indexing, an interactive entity graph, source inspection, corrections, query history and bounded model usage. It uses the original GraphRAG 0.1.1 extraction, Leiden clustering, local/global search and community report components, with Qwen2-0.5B and MiniLM in a separate local inference process.

**Evidence exploration works; generated answers remain experimental.** On twelve owned questions, vector and local retrieval achieved 0.95 mean required-document recall, versus 0.70 for global retrieval. None of the three modes produced an answer that passed the output contract. Failed answers are withheld while their retrieved passages remain inspectable. Read the [measured results](docs/evaluation.md) before relying on model output.

## Run the workspace

The supplied Compose profile targets an Apple Silicon workstation: the model container runs Linux ARM64, while the original graph runtime runs Linux AMD64 through Docker emulation. Allow approximately 8 GiB for the stack and additional space for images and immutable model files. The application uses exact cosine search over SQLite embeddings; it does not depend on Lance native vector execution under emulation.

```sh
python3 scripts/fetch_models.py .models
docker compose up -d --build
docker compose ps
```

Open **http://localhost:8089**, wait for readiness, and choose **Load sample corpus**. Initial scientific imports and model loading can take several minutes. The worker extracts and indexes the twelve example documents. Once jobs complete:

1. Select an entity and read the original passage behind its relationship.
2. Flag a relationship with a reason. Its passage is excluded from all retrieval modes until the correction is restored.
3. Edit a document in **Documents** and save a new revision. Old derived evidence becomes unavailable immediately.
4. Compare the three retrieval modes, inspect the returned passages and review any model-contract failure.
5. Use **Indexing** to inspect usage, cancel a job or retry a failed attempt.

This is a workspace for one trusted local operator. It has no user authentication or tenant isolation. Compose publishes the UI/API only on loopback; do not expose it directly to a network. Model weights are mounted read-only and all three services run as a non-root user with resource limits.

Set `GRAPH_MODELS` to an existing verified model cache or `EXPLORER_PORT` to change the public loopback port. Models are always checked against [the immutable file manifest](dependencies/models.json). No cloud API key is required.

## Develop and verify

Python 3.10 and Node 20.10 are the supported development versions. [Dependency setup](docs/dependencies.md) covers the separate graph and model environments, original LanceDB artifact reconstruction and platform constraints.

```sh
python -m unittest discover -s tests
npm ci --prefix web
npm test --prefix web
npm run build --prefix web
```

For native development, start the model environment with `python -m explorer.model_service --models .models`, then use the graph environment in separate terminals:

```sh
python -m explorer.api
python -m explorer.worker
```

The API serves `web/dist` and owns one process lease for its database. Browser tests require a seeded, indexed workspace and a stopped indexing worker so the explicit cancellation journey cannot race automatic processing. Set `CHROME_PATH` to Chrome's executable and, if needed, `EXPLORER_URL` to the API origin, then run `npm run test:browser --prefix web`.

See the [architecture](docs/architecture.md), [operator and recovery runbook](docs/runbook.md), [HTTP API](docs/api.md), [evaluation](docs/evaluation.md) and [third-party notices](THIRD_PARTY_NOTICES.md). Controlled model fixtures test failures and concurrency; the recorded evaluation and packaged browser journey use actual local inference.
