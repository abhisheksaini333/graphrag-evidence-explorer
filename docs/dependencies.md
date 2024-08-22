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
