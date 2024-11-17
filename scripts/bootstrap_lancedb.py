"""Repackage verified original LanceDB binaries after their PyPI removal.

Only the distribution container and its RECORD are rebuilt. Upstream package
code, native binaries, WHEEL, METADATA and license content remain unchanged.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import platform
import tarfile
import tempfile
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def platform_record(name):
    records = json.loads((ROOT / "dependencies/lancedb-originals.json").read_text())
    if name not in records:
        raise ValueError(
            "Supported profiles are darwin-arm64 and linux-x86_64 with Python3.10"
        )
    return records[name]


def repack(source, destination, expected_hash):
    source, destination = Path(source), Path(destination)
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("Original LanceDB archive checksum mismatch")
    import zstandard

    files, licenses, total = {}, {}, 0
    prefix = "lib/python3.10/site-packages/"
    with zipfile.ZipFile(source) as archive:
        for name in archive.namelist():
            if not name.endswith(".tar.zst"):
                continue
            with archive.open(name) as compressed:
                with zstandard.ZstdDecompressor().stream_reader(compressed) as reader:
                    with tarfile.open(fileobj=reader, mode="r|") as tar:
                        for member in tar:
                            path = PurePosixPath(member.name)
                            if path.is_absolute() or ".." in path.parts:
                                raise ValueError("Unsafe path in upstream archive")
                            if not member.isfile():
                                continue
                            if not member.name.startswith((prefix, "info/licenses/")):
                                continue
                            total += member.size
                            if total > 256 * 1024 * 1024:
                                raise ValueError(
                                    "Archive contents exceed the bootstrap bound"
                                )
                            data = tar.extractfile(member).read()
                            if member.name.startswith(prefix):
                                files[member.name[len(prefix) :]] = data
                            else:
                                licenses[path.name] = data
    wheel_files = [name for name in files if name.endswith(".dist-info/WHEEL")]
    if len(wheel_files) != 1:
        raise ValueError("Expected one original wheel metadata record")
    dist = wheel_files[0].rsplit("/", 1)[0]
    tags = [
        line[5:]
        for line in files[wheel_files[0]].decode().splitlines()
        if line.startswith("Tag: ")
    ]
    if len(tags) != 1 or "/" in tags[0] or "\\" in tags[0]:
        raise ValueError("Ambiguous platform tag")
    for name, data in licenses.items():
        files[dist + "/license_files/" + name] = data
    record_name = dist + "/RECORD"
    files.pop(record_name, None)
    rows = io.StringIO(newline="")
    writer = csv.writer(rows, lineterminator="\n")
    for name, data in sorted(files.items()):
        digest = (
            base64.urlsafe_b64encode(hashlib.sha256(data).digest())
            .rstrip(b"=")
            .decode()
        )
        writer.writerow((name, "sha256=" + digest, len(data)))
    writer.writerow((record_name, "", ""))
    files[record_name] = rows.getvalue().encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as wheel:
        for name, data in sorted(files.items()):
            item = zipfile.ZipInfo(name)
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o644 << 16
            wheel.writestr(item, data)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / ("lancedb-0.9.0-" + tags[0] + ".whl")
    payload = output.getvalue()
    if target.exists() and target.read_bytes() != payload:
        raise FileExistsError("Refusing to replace a different existing wheel")
    target.write_bytes(payload)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform",
        default=platform.system().lower() + "-" + platform.machine().lower(),
    )
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path, default=Path(".deps"))
    args = parser.parse_args()
    record = platform_record(args.platform)
    with tempfile.TemporaryDirectory(prefix="lancedb-original-") as temp:
        source = args.archive or Path(temp) / "original.conda"
        if args.archive is None:
            url = record["download_url"]
            urllib.request.urlretrieve(
                "https:" + url if url.startswith("//") else url, source
            )
        print(repack(source, args.output, record["sha256"]))


if __name__ == "__main__":
    main()
