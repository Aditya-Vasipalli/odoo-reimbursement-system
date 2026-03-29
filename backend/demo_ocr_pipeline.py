from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFilter

from backend.routers.ocr import router as ocr_router


DEMO_DIR = Path(__file__).resolve().parent / "demo_receipts"


def make_receipt_image(lines: list[str], output_path: Path, blur: float = 0.0) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1200, 700), "white")
    draw = ImageDraw.Draw(img)

    y = 60
    for line in lines:
        draw.text((60, y), line, fill="black")
        y += 95

    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(blur))

    img.save(output_path)


def post_image(client: TestClient, image_path: Path) -> tuple[int, dict[str, Any]]:
    with image_path.open("rb") as fh:
        response = client.post(
            "/ocr/scan",
            files={"file": (image_path.name, fh.read(), "image/png")},
        )
    return response.status_code, response.json()


def summarize_result(name: str, status_code: int, body: dict[str, Any]) -> str:
    amount = body.get("amount")
    date = body.get("date")
    vendor = body.get("vendor")
    currency = body.get("currency")
    return (
        f"[{name}] status={status_code} "
        f"amount={amount} date={date} vendor={vendor} currency={currency}"
    )


def main() -> None:
    app = FastAPI()
    app.include_router(ocr_router)
    client = TestClient(app)

    receipt_files = [
        (
            "receipt_usd.png",
            ["DEMO MART", "Date: 2026-03-29", "Total: $123.45", "Thank you"],
            0.0,
        ),
        (
            "receipt_inr.png",
            ["CITY CAFE", "29/03/2026", "Rs. 450", "Visit again"],
            0.0,
        ),
        (
            "receipt_eur_blur.png",
            ["BISTRO EUROPA", "March 29, 2026", "Total: EUR 78.90", "Grazie"],
            0.6,
        ),
    ]

    print("Generating demo receipts in:", DEMO_DIR)
    for filename, lines, blur in receipt_files:
        make_receipt_image(lines, DEMO_DIR / filename, blur=blur)

    print("\nRunning OCR through /ocr/scan endpoint...")
    for filename, _, _ in receipt_files:
        status_code, body = post_image(client, DEMO_DIR / filename)
        print(summarize_result(filename, status_code, body))

    print("\nEdge-case checks...")
    non_image_resp = client.post(
        "/ocr/scan",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    print("[non-image] status=", non_image_resp.status_code)

    big_payload = b"\x89PNG\r\n\x1a\n" + (b"0" * (5 * 1024 * 1024 + 64))
    big_file_resp = client.post(
        "/ocr/scan",
        files={"file": ("big.png", big_payload, "image/png")},
    )
    print("[big-file] status=", big_file_resp.status_code)

    blank = Image.new("RGB", (800, 400), "white")
    blank_buf = BytesIO()
    blank.save(blank_buf, format="PNG")
    unreadable_resp = client.post(
        "/ocr/scan",
        files={"file": ("blank.png", blank_buf.getvalue(), "image/png")},
    )
    print("[unreadable] status=", unreadable_resp.status_code, "body=", unreadable_resp.json())


if __name__ == "__main__":
    main()
