# Operating the evidence workspace

## Startup and diagnosis

`docker compose ps` should show a healthy model and API plus a running worker. Model readiness follows file hash verification and model loading. API readiness follows scientific-runtime import, database migration, exclusive process ownership and abandoned API-query recovery. Health does not assert model answer quality. A second API process using the same database refuses ownership.

Use `docker compose logs --tail 100 graph-model graph-api graph-worker`. Model busy/timeouts fail closed; indexing records a bounded failure instead of inventing evidence. If the API process dies during inference, its running query is marked abandoned at restart. CLI evaluations own distinct records and are not incorrectly abandoned by API startup.

Cancellation prevents later publication, but cannot instantly stop a CPU call already inside the model process. Wait for its deadline before retrying. A killed worker's lease must expire before another worker claims the job. Pending call reservations remain charged to prevent crash/retry budget bypass.

## Backup and separate restore

The SQLite backup API takes a consistent live snapshot, checks integrity and foreign keys, and refuses an existing destination. Store backups outside the public repository and protect them as source content.

For a native database:

```sh
python -m explorer.backup .data/corpus.sqlite /private/backups/corpus.sqlite
```

For Compose, choose a unique file name inside the data volume, then copy it out:

```sh
docker compose exec graph-api python -m explorer.backup /data/corpus.sqlite /data/corpus-backup.sqlite
docker compose cp graph-api:/data/corpus-backup.sqlite ./corpus-backup.sqlite
```

Copy a verified backup to a **new** directory and start an isolated API with `--database /new/location/corpus.sqlite --port 8099`. Never replace the live database while services are using it. Compare document, passage and claim counts, inspect source text and confirm the backup hash stays unchanged. Delete a temporary volume backup only after verifying your external copy.

## Evaluate and reproduce recovery

After indexing the sample corpus, stop automatic indexing to keep the comparison generation fixed:

```sh
docker compose stop graph-worker
docker compose exec graph-api python -m explorer.evaluate --database /data/corpus.sqlite --model-url http://graph-model:8090 --output /data/evaluation.json
docker compose cp graph-api:/data/evaluation.json ./evaluation.json
```

The output includes the question-file hash, all thirty-six case/mode records, retrieval recall, lexical answer-term coverage, abstention, actual token usage and latency. Lexical coverage is not semantic accuracy. Reusing the same cases after a prompt revision is a repeat evaluation, not an independent held-out result.

`python -m explorer.recovery_probe --help` describes the native process-kill demonstration. It creates a separate database, kills an actual worker after the first publication, waits for real lease expiry and checks that completed extraction/embedding calls were not repeated. Keep its output directory separate from the live corpus.

Use `docker compose stop` to preserve all data. `docker compose down` preserves named volumes unless explicitly given a volume-removal flag. Back up before changing runtime versions, model manifests, prompt profiles or schemas. Never reuse an index generated under a different profile.
