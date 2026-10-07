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
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
WINDOWS_INVALID_CHARS = set('<>:"/\\|?*')


def next_document_number(output_dir: Path) -> int:
    numbers = [
        int(match.group(1))
        for path in output_dir.iterdir()
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


def choose_dpi(current_dpi: int = SCAN_DPI) -> int:
    while True:
        other_dpi = 150 if current_dpi == 300 else 300
        answer = input(
            f"Scan DPI [{current_dpi}/{other_dpi}] (Enter for {current_dpi}): "
        ).strip()
        if not answer:
            return current_dpi
        if answer == str(current_dpi):
            return current_dpi
        if answer == "150":
            return 150
        if answer == "300":
            return 300
        print("[ERROR] Please enter 150 or 300.")


def validate_session_name(name: str) -> str | None:
    if not name or name.isspace():
        return "Folder name cannot be empty."
    if name in (".", ".."):
        return "Folder name cannot be . or ..."
    if name != name.rstrip(" ."):
        return "Folder name cannot end with a space or period."
    if any(ord(character) < 32 for character in name):
        return "Folder name cannot contain control characters."
    invalid = sorted(set(name) & WINDOWS_INVALID_CHARS)
    if invalid:
        return f"Folder name cannot contain: {' '.join(invalid)}"
    device_name = name.split(".", 1)[0].upper()
    if device_name in WINDOWS_RESERVED_NAMES:
        return f"{name} is a reserved Windows name."
    return None


def choose_session_directories() -> tuple[Path, Path]:
    while True:
        answer = input("Create a folder for this session? [y/N] ").strip().lower()
        if answer in ("", "n", "no"):
            SCANS.mkdir(exist_ok=True)
            TEMP.mkdir(exist_ok=True)
            return SCANS, TEMP
        if answer in ("y", "yes"):
            break
        print("[ERROR] Please enter y or n.")

    while True:
        name = input("Session folder name: ")
        error = validate_session_name(name)
        if error:
            print(f"[ERROR] {error}")
            continue
        output_dir = SCANS / name
        temp_dir = output_dir / "temp"
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"[ERROR] Could not create the session folder: {exc}")
            continue
        print(f"Output folder: {output_dir.resolve()}")
        return output_dir, temp_dir


def show_document(document: int) -> None:
    print(f"\n{'-' * 42}\nDocument {document:03d}\n{'-' * 42}\n")


def choose_action(dpi: int) -> str:
    print("\nChoose next action:")
    print("  [n] Scan next page of the same document")
    print("  [d] Finish this document, save it, and start a new one")
    print("  [x] Finish this document, save it, and exit")
    print("  [q] Quit without saving current unsaved pages")
    print(f"  [s] Settings - change scan DPI (current: {dpi})")
    return input("\nEnter choice: ").strip().lower()


def scan_next_page(
    scanner: Scanner,
    document: int,
    pages: list[Path],
    dpi: int,
    temp_dir: Path,
) -> None:
    page_number = len(pages) + 1
    label = "page 1" if page_number == 1 else "the next page"
    input(f"Place {label} on the scanner, then press ENTER to scan.")
    path = temp_dir / f"document_{document:03d}_page_{page_number:03d}.bmp"
    print(f"\nScanning page {page_number} at {dpi} DPI...")
    try:
        scan_page(scanner, path, dpi)
    except ScannerError as exc:
        print(f"[ERROR] Scan failed: {exc}\nPage {page_number} was not added. Use n to retry.")
        return
    pages.append(path)
    print(f"[OK] Page {page_number} added")


def save_document(document: int, pages: list[Path], output_dir: Path) -> bool:
    if not pages:
        print("[ERROR] No pages to save. Use n to scan a page.")
        return False
    output = output_dir / f"document_{document:03d}.pdf"
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


def remove_session_temp(output_dir: Path, temp_dir: Path) -> None:
    if temp_dir != output_dir / "temp":
        return
    try:
        temp_dir.rmdir()
    except FileNotFoundError:
        pass
    except OSError as exc:
        print(f"[WARNING] Could not remove the session temp folder: {exc}")


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
    output_dir, temp_dir = choose_session_directories()
    document = next_document_number(output_dir)
    pages: list[Path] = []
    show_document(document)
    scan_next_page(scanner, document, pages, dpi, temp_dir)
    while True:
        command = choose_action(dpi)
        if command == "n":
            scan_next_page(scanner, document, pages, dpi, temp_dir)
        elif command in ("d", "x"):
            if save_document(document, pages, output_dir):
                if command == "x":
                    remove_session_temp(output_dir, temp_dir)
                    try:
                        os.startfile(output_dir.resolve())
                    except OSError as exc:
                        print(f"[WARNING] Could not open the output folder: {exc}")
                    print("Done.")
                    return 0
                document = next_document_number(output_dir)
                print(f"\nStarting Document {document:03d}...")
                show_document(document)
                scan_next_page(scanner, document, pages, dpi, temp_dir)
        elif command == "q":
            if pages and input("[WARNING] Current document has unsaved pages. Quit without saving? [y/N] ").strip().lower() != "y":
                continue
            remove_pages(pages)
            print("Quit.")
            return 0
        elif command == "s":
            dpi = choose_dpi(dpi)
            print(f"[OK] Scan DPI changed to {dpi}. The next page will use this setting.")
        else:
            print("[ERROR] Invalid choice. Please enter n, d, x, q, or s.")


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted. Unsaved temporary pages remain in temp/.")
        raise SystemExit(130)
