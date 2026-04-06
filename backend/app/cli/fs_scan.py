from __future__ import annotations

import argparse
import asyncio
import json

from backend.app.db import SessionLocal
from backend.app.adapters.filesystem.scanner import scan_file_source


async def _run(source_id: str) -> dict:
    with SessionLocal() as session:
        return await scan_file_source(session, source_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan a filesystem source and ingest changed files.")
    parser.add_argument("source_id", help="FileSource UUID to scan")
    args = parser.parse_args()
    result = asyncio.run(_run(args.source_id))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
