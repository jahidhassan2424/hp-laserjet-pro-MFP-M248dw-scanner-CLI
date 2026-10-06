"""Interactive single-page-at-a-time USB scanning CLI."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from pdf_utils import create_pdf, remove_pages
from scanner import SCAN_DPI, Scanner, ScannerError, list_scanners, scan_page


ROOT = Path(__file__).resolve().parent
SCANS = ROOT / "scans"
TEMP = ROOT / "temp"
DOCUMENT_PATTERN = re.compile(r"document_(\d+)\.pdf", re.IGNORECASE)


def next_document_number() -> int:
    numbers = [
        int(match.group(1))
        for path in SCANS.iterdir()
        if (match := DOCUMENT_PATTERN.fullmatch(path.name))
    ]
    return max(numbers, default=0) + 1


def choose_scanner(scanners: list[Scanner]) -> Scanner | None:
    if not scanners:
        print("No USB WIA scanner found. Run --list-scanners after checking the USB cable and driver.")
        return None
    if len(scanners) == 1:
        return scanners[0]
    print("USB scanners:")
    for number, scanner in enumerate(scanners, 1):
        print(f"  {number}. {scanner.name} ({scanner.port})")
    while True:
        answer = input("Select scanner number (or q to quit): ").strip().lower()
        if answer == "q":
            return None
        if answer.isdecimal() and 1 <= int(answer) <= len(scanners):
            return scanners[int(answer) - 1]
        print("Enter a listed number or q.")


def choose_dpi() -> int:
    while True:
        answer = input(f"Scan DPI [{SCAN_DPI}/150] (Enter for {SCAN_DPI}): ").strip()
        if not answer or answer == str(SCAN_DPI):
            return SCAN_DPI
        if answer == "150":
            return 150
        print("[ERROR] Please enter 150 or 300.")


def show_document(document: int) -> None:
    print(f"\n{'-' * 42}\nDocument {document:03d}\n{'-' * 42}\n")


def choose_action() -> str:
    print("\nChoose next action:")
    print("  [n] Scan next page of the same document")
    print("  [d] Finish this document, save it, and start a new one")
    print("  [x] Finish this document, save it, and exit")
    print("  [q] Quit without saving current unsaved pages")
    return input("\nEnter choice: ").strip().lower()


def scan_next_page(scanner: Scanner, document: int, pages: list[Path], dpi: int) -> None:
    page_number = len(pages) + 1
    label = "page 1" if page_number == 1 else "the next page"
    input(f"Place {label} on the scanner, then press ENTER to scan.")
    path = TEMP / f"document_{document:03d}_page_{page_number:03d}.bmp"
    print(f"\nScanning page {page_number} at {dpi} DPI...")
    try:
        scan_page(scanner, path, dpi)
    except ScannerError as exc:
        print(f"[ERROR] Scan failed: {exc}\nPage {page_number} was not added. Use n to retry.")
        return
    pages.append(path)
    print(f"[OK] Page {page_number} added")


def save_document(document: int, pages: list[Path]) -> bool:
    if not pages:
        print("[ERROR] No pages to save. Use n to scan a page.")
        return False
    output = SCANS / f"document_{document:03d}.pdf"
    if output.exists():
        print(f"[ERROR] PDF already exists: {output}. Move it before trying again.")
        return False
    try:
        create_pdf(pages, output)
    except Exception as exc:
        print(f"[ERROR] Could not save PDF: {exc}. Scanned pages are still available.")
        return False
    print(f"\n[OK] Saved:\n{output}")
    try:
        remove_pages(pages)
    except OSError as exc:
        print(f"[WARNING] Could not remove some temporary pages: {exc}")
    pages.clear()
    return True


def run() -> int:
    parser = argparse.ArgumentParser(description="Scan USB flatbed pages into numbered PDFs.")
    parser.add_argument("--list-scanners", action="store_true", help="Test WIA USB scanner detection and exit")
    args = parser.parse_args()
    try:
        scanners = list_scanners()
    except ScannerError as exc:
        print(f"[ERROR] {exc}")
        return 1
    if args.list_scanners:
        if not scanners:
            print("No USB WIA scanners found.")
            return 1
        for scanner in scanners:
            print(f"{scanner.name} ({scanner.port})")
        return 0
    os.system("cls")
    print(f"{'=' * 42}\n         HP USB Scanner CLI\n{'=' * 42}\n")
    scanner = choose_scanner(scanners)
    if scanner is None:
        return 1 if not scanners else 0
    print(f"Scanner: {scanner.name}\nMode:    USB")
    dpi = choose_dpi()
    print(f"DPI:     {dpi}")
    SCANS.mkdir(exist_ok=True)
    TEMP.mkdir(exist_ok=True)
    document = next_document_number()
    pages: list[Path] = []
    show_document(document)
    scan_next_page(scanner, document, pages, dpi)
    while True:
        command = choose_action()
        if command == "n":
            scan_next_page(scanner, document, pages, dpi)
        elif command in ("d", "x"):
            if save_document(document, pages):
                if command == "x":
                    print("Done.")
                    return 0
                document = next_document_number()
                print(f"\nStarting Document {document:03d}...")
                show_document(document)
                scan_next_page(scanner, document, pages, dpi)
        elif command == "q":
            if pages and input("[WARNING] Current document has unsaved pages. Quit without saving? [y/N] ").strip().lower() != "y":
                continue
            remove_pages(pages)
            print("Quit.")
            return 0
        else:
            print("[ERROR] Invalid choice. Please enter n, d, x, or q.")


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted. Unsaved temporary pages remain in temp/.")
        raise SystemExit(130)
