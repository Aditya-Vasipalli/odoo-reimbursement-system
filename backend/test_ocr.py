from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.services.ocr_service import extract_receipt_data


def run_one(path: Path) -> dict:
    try:
        image_bytes = path.read_bytes()
    except OSError as exc:
        return {"file": str(path), "error": f"read_failed: {exc}"}

    try:
        data = extract_receipt_data(image_bytes)
    except Exception as exc:
        return {"file": str(path), "error": f"ocr_failed: {exc}"}

    return {"file": str(path), "result": data}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run OCR extraction on 2-3 sample receipt images for demo prep."
    )
    parser.add_argument("images", nargs="+", help="Receipt image file paths")
    args = parser.parse_args()

    for image in args.images:
        print(json.dumps(run_one(Path(image)), indent=2))


if __name__ == "__main__":
    main()
