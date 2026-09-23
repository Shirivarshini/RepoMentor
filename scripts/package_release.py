"""Create a reproducible source handoff without credentials, caches or dependencies."""
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'deliverables'
EXCLUDED = {'.git', '.venv', 'venv', 'node_modules', 'dist', '__pycache__',
            '.pytest_cache', '.ruff_cache', '.mypy_cache', '.codex', '.agents',
            'deliverables', 'mnt'}


def main():
    OUTPUT.mkdir(exist_ok=True)
    archive = OUTPUT / 'RepoMentor_Phase9_Source.zip'
    entries = []
    with ZipFile(archive, 'w', ZIP_DEFLATED) as bundle:
        for directory, folders, files in os.walk(ROOT):
            folders[:] = sorted(f for f in folders if f not in EXCLUDED)
            for filename in sorted(files):
                path = Path(directory) / filename
                if (filename.startswith('.env') and filename != '.env.example') or path.suffix in {'.pyc', '.tsbuildinfo', '.log', '.zip'}:
                    continue
                relative = path.relative_to(ROOT).as_posix()
                # Old exported copies are not application entry points.
                if relative in {'main.py', 'LandingPage.tsx'}:
                    continue
                bundle.write(path, 'RepoMentor/' + relative)
                entries.append(relative)
    manifest = {'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'file_count': len(entries), 'files': entries}
    (OUTPUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    with ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert not any(n.endswith('/.env') for n in bundle.namelist())
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}))


if __name__ == '__main__':
    main()
