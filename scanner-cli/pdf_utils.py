"""Build a PDF from ordered scan files."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Sequence

import img2pdf
import pikepdf


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


def pdf_page_count(pdf_path: Path) -> int:
    with pikepdf.Pdf.open(pdf_path) as pdf:
        return len(pdf.pages)


def append_image_to_pdf(image_path: Path, output_pdf_path: Path) -> None:
    """Append one scanned image to an existing PDF without losing its pages."""
    with NamedTemporaryFile(suffix=".pdf", dir=output_pdf_path.parent, delete=False) as file:
        page_pdf = Path(file.name)
    with NamedTemporaryFile(suffix=".pdf", dir=output_pdf_path.parent, delete=False) as file:
        updated_pdf = Path(file.name)
    try:
        with page_pdf.open("wb") as output:
            img2pdf.convert(str(image_path), outputstream=output)
        with pikepdf.Pdf.open(output_pdf_path) as document:
            with pikepdf.Pdf.open(page_pdf) as page:
                document.pages.extend(page.pages)
            updated_pdf.unlink(missing_ok=True)
            document.save(updated_pdf)
        updated_pdf.replace(output_pdf_path)
    finally:
        page_pdf.unlink(missing_ok=True)
        updated_pdf.unlink(missing_ok=True)
