# Upstream components

The original application source is MIT licensed. Dependency and model licenses remain separate:

| Component | License | Source |
|---|---|---|
| Microsoft GraphRAG0.1.1 | MIT | https://github.com/microsoft/graphrag/tree/v0.1.1 |
| LanceDB0.9.0 | Apache2.0 | https://github.com/lancedb/lancedb/tree/python-v0.9.0 |
| Qwen2-0.5B-Instruct | Apache2.0 | https://huggingface.co/Qwen/Qwen2-0.5B-Instruct |
| all-MiniLM-L6-v2 | Apache2.0 | https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 |

The LanceDB bootstrap verifies a preserved conda-forge package, keeps original code/binaries/metadata/license bytes, and creates a wheel container with an updated file RECORD. It does not reconstruct or change upstream release metadata. Exact source URLs and hashes are in `dependencies/lancedb-originals.json`. Remaining transitive licenses are supplied by their distributions. No model weights or upstream source trees are included in this repository.
