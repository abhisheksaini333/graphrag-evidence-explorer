# Retrieval and model results

The evaluation uses twelve owned service-ownership documents and twelve fixed questions covering direct lookup, multiple relationships, communities, conflicting evidence, negation and abstention. Every mode sees the same source snapshot, original Qwen2-0.5B checkpoint and MiniLM encoder. The corpus is deliberately small; it does not establish performance on external organizational data.

## Actual inference

All twelve documents indexed successfully in the native run, producing twelve supported claims from twelve passages. The extractor missed additional assertions: successful indexing does not mean complete extraction.

The first evaluation produced zero valid answers in all modes. A separate format-calibration exercise then motivated one general JSON-contract adapter revision. Repeating the same fixed questions produced the following results. This repeat is not an independent held-out evaluation.

| Mode | Questions | Mean required-document recall | Answers accepted | Correct abstentions | Mean seconds | Model calls | Actual tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Vector | 12 | 0.95 | 0 | 0 | 5.989 | 24 | 2,953 |
| Local graph | 12 | 0.95 | 0 | 0 | 3.834 | 24 | 2,950 |
| Global graph | 12 | 0.70 | 0 | 0 | 3.733 | 24 | 2,904 |

Hardware: Apple M3 Pro,11 logical CPUs,18 GiB memory, two inference threads. Durations include local orchestration and model calls and vary with machine load. Global mode failed at its map-output contract, so these timings and calls do not represent successful full map/reduce answers. Context truncation and small-community balancing can reduce global recall.

Generated responses included missing/empty citations, unexpected fields and unsupported answers. The gate withheld them. Citation validation would establish that a cited passage exists, not that an accepted answer follows from it. Lexical answer-term coverage was zero; even a nonzero value would not establish semantic accuracy.

One actual community-report probe produced invented membership wording and a nonnumeric rating. The original framework schema rejected it. No successful community report is claimed from that probe. Deterministic contract tests exercise valid framework integration separately from model quality.

## Recovery and operations

A real child indexing process was stopped and killed after publishing its first passage. After real lease expiry, a fresh child completed the second passage. Both completed first-passage model calls remained unchanged: no duplicate extraction or embedding call was charged. The successful probe used a90-second lease; an earlier10-second probe expired before publication and is retained in development evidence.

A live SQLite snapshot passed integrity and foreign-key checks. A separate restore exposed the same twelve documents, twelve claims and twelve passages without changing the original backup. Native API startup warmed scientific imports before reporting readiness; first graph access then took0.009 seconds after an11.701-second startup.

## Read the evidence

The JSON records in [evidence](evidence/) contain the original per-case comparison, repeated comparison, actual community output, process-recovery result and restore checks. Raw model failures are retained rather than counted as successful answers. Browser and container proofs test packaged behavior; hosted CI separately tests the native Linux application and frontend build.

The useful default workflow is inspecting and correcting source-linked evidence. The measured results do not support replacing vector retrieval with this graph configuration or relying on its generated answers. A larger model, richer extraction and a new independent evaluation would need their own measured acceptance criteria.
