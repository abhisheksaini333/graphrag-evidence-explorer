"""Create a verified SQLite snapshot without replacing existing backup files."""
import argparse,hashlib,json,os,sqlite3
from pathlib import Path


def backup(source,destination):
    source,destination=Path(source),Path(destination)
    if not source.is_file() or source.resolve()==destination.resolve():raise ValueError('Choose an existing database and a new backup path')
    descriptor=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(descriptor)
    original=snapshot=None
    try:
        original=sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)
        snapshot=sqlite3.connect(destination)
        original.backup(snapshot,pages=128,sleep=.05)
        integrity=snapshot.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity!='ok' or snapshot.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Snapshot verification failed')
        tables=[row[0] for row in snapshot.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        counts={name:snapshot.execute('SELECT COUNT(*) FROM "'+name.replace('"','""')+'"').fetchone()[0] for name in tables}
        snapshot.close();snapshot=None
        return {'integrity':integrity,'tables':counts,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'destination':str(destination)}
    except BaseException:
        destination.unlink(missing_ok=True);raise
    finally:
        if snapshot:snapshot.close()
        if original:original.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source');parser.add_argument('destination')
    args=parser.parse_args();print(json.dumps(backup(args.source,args.destination),indent=2))
