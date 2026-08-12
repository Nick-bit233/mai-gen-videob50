from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.video_metadata import build_desktop_manifest  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the reviewed desktop maimai video metadata manifest."
    )
    parser.add_argument("--input", required=True, type=Path, help="Full reviewed manifest")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "video_metadata" / "asset-manifest.json",
        help="Desktop manifest output path",
    )
    return parser.parse_args()


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def main() -> int:
    args = parse_args()
    with args.input.open("r", encoding="utf-8") as handle:
        source_payload = json.load(handle)
    desktop_manifest = build_desktop_manifest(source_payload)
    write_json_atomic(args.output, desktop_manifest)
    print(
        "Built desktop video metadata: "
        f"version={desktop_manifest['metadata_store_version']} "
        f"assets={len(desktop_manifest['assets'])} "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
