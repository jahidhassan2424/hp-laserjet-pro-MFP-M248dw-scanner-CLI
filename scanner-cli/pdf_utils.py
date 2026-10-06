"""Build a PDF from ordered scan files."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import img2pdf


def create_pdf(image_paths: Sequence[Path], output_pdf_path: Path) -> Path:
    """Save one PDF without overwriting an existing document."""
    if not image_paths:
        raise ValueError("Cannot create a PDF without pages.")
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with output_pdf_path.open("xb") as output:
            created = True
            img2pdf.convert(*(str(path) for path in image_paths), outputstream=output)
    except Exception:
        if created:
            output_pdf_path.unlink(missing_ok=True)
        raise
    return output_pdf_path


def remove_pages(image_paths: Sequence[Path]) -> None:
    for path in image_paths:
        path.unlink(missing_ok=True)
