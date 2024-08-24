"""Fetch immutable model revisions; verify every model file before using it."""
import argparse
from pathlib import Path
import sys
import tempfile
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from explorer.models import model_manifest,sha256_file,verify_model


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    for specification in model_manifest().values():
        target=args.directory/specification['directory']
        if not args.verify_only:
            target.mkdir(parents=True,exist_ok=True)
            for item in specification['files']:
                path=target/item['file']
                if path.exists():
                    if sha256_file(path)!=item['sha256']:
                        raise SystemExit('Existing model artifact differs: '+item['file'])
                    continue
                with tempfile.NamedTemporaryFile(dir=target,delete=False) as handle:
                    partial=Path(handle.name)
                try:
                    urllib.request.urlretrieve(item['url'],partial)
                    if sha256_file(partial)!=item['sha256']:
                        raise SystemExit('Downloaded model checksum mismatch')
                    partial.replace(path)
                finally:
                    partial.unlink(missing_ok=True)
        verify_model(target,specification)
        print(specification['model']+' '+specification['revision']+' verified')


if __name__=='__main__':main()
