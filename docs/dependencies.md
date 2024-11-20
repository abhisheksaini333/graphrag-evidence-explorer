# Reproducible Python runtime

Use Python3.10 on macOS ARM64 or native Linux x86-64. Install the small bootstrap dependency, reconstruct the removed LanceDB distribution from its checksum-verified original, then install the complete locked graph profile:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install zstandard==0.22.0
python scripts/bootstrap_lancedb.py --output .deps
python -m pip install --find-links .deps -r requirements.txt
python -m pip check
```

`requirements.txt` freezes all122 graph-runtime packages. `dependencies/python-provenance.json` records original artifact metadata; the complete selected profile is available by July15,2024. The bootstrap retains the original license and verifies source archives before reading their contents. Its newly assembled wheel is reproducible; original Python and native library bytes are unchanged.

Native Mac integration is verified. Intel Linux imports work under Docker emulation on Apple silicon, but Lance native vector scans crash in that emulated combination. The bounded application uses exact cosine retrieval over stored embeddings, rather than depending on that native index. Native Linux CI must verify the application separately. Linux ARM supports the preserved Lance binary but the full graph profile requires an additional graspologic-native build; it is not the default supported installer target.

## Separate model environment

The original model dependencies conflict with parts of the graph profile. Keep them in a separate environment and connect over the local model HTTP contract:

```sh
python3.10 -m venv .model-venv
.model-venv/bin/pip install -r model-requirements.txt
.model-venv/bin/pip check
python3 scripts/fetch_models.py .models
.model-venv/bin/python -m explorer.model_service --models .models
```

`dependencies/model-runtime-provenance.json` records the23 selected versions; `dependencies/models.json` records immutable upstream revisions, individual URLs and SHA256 values. Do not substitute a later checkpoint behind the same model name. To use an existing cache, run `scripts/fetch_models.py CACHE --verify-only` first.

## Hashed containers

The Dockerfiles use independent graph Linux x86-64 and model Linux ARM64 locks, including a hashed zstandard bootstrap lock. Pip installs with `--no-deps --require-hashes`, then checks the complete dependency graph. Selected wheel/source hashes and publication metadata are in `dependencies/*linux*.json`. Swifter1.4 is distributed as an original source archive and builds with the pinned base image's Python tooling. The reconstructed LanceDB wheel has a deterministic local hash; its original package/library bytes and upstream licenses are preserved.

Both images pin the Python3.10.11 Bullseye manifest by digest; the frontend builder pins Node20.10 by digest. Runtime images contain only source, locked dependencies and built frontend assets. Model weights and live data are external mounts. The graph image requires AMD64 and the model image requires ARM64; changing these platforms requires a new artifact/ABI audit, not just removing the architecture guard.
