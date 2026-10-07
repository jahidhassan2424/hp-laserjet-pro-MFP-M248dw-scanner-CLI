"""Interactive single-page-at-a-time USB scanning CLI."""

from __future__ import annotations

import argparse
import os
import re
import uuid
from pathlib import Path

from pdf_utils import append_image_to_pdf, create_pdf, pdf_page_count, remove_pages
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


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def choose_dpi(current_dpi: int = SCAN_DPI) -> int:
    while True:
        clear_screen()
        print("Scan DPI")
        print("[1] 300")
        print("[2] 150")
        answer = input("Enter choice: ").strip()
        if not answer:
            return current_dpi
        if answer == "1":
            return 300
        if answer == "2":
            return 150
        print("[ERROR] Invalid choice. Please enter 1 or 2.")


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


def choose_action(output_dir: Path, document: int, pages: list[Path], dpi: int) -> str:
    aliases = {
        "n": "n",
        "1": "n",
        "d": "d",
        "2": "d",
        "x": "x",
        "3": "x",
        "q": "q",
        "4": "q",
        "s": "s",
        "*": "s",
        "m": "m",
        "w": "w",
        "r": "r",
    }
    # A scan can take long enough for accidental Enter presses to remain in the
    # Windows console input buffer. Clear them before showing this menu, then
    # keep Enter as the deliberate default once the menu is visible.
    discard_pending_console_input()
    while True:
        render_dashboard(output_dir, document, pages, dpi)
        has_pages = bool(pages)
        print("\nChoose next action:")
        print(f"  [n or 1] Scan next page{' (default)' if not has_pages else ''}")
        print(f"  [d or 2] Finish this, save and start new{' (default)' if has_pages else ''}")
        print("  [x or 3] Finish this and exit")
        print("  [q or 4] Quit without saving")
        print(f"  [s or *] Change DPI (current: {dpi})")
        print("  [w] Save current")
        print("  [r] Discard current")
        print("  [m] Manage saved documents")
        answer = input("\nEnter choice: ").strip().lower()
        if not answer:
            return "d" if has_pages else "n"
        command = aliases.get(answer)
        if command:
            return command
        print("[ERROR] Choose n/1, d/2, x/3, q/4, s/*, w, r, or m.")


def discard_pending_console_input() -> None:
    if os.name != "nt":
        return
    import msvcrt

    while msvcrt.kbhit():
        msvcrt.getwch()


def scan_next_page(
    scanner: Scanner,
    document: int,
    pages: list[Path],
    dpi: int,
    temp_dir: Path,
) -> None:
    page_number = len(pages) + 1
    label = "page 1" if page_number == 1 else "the next page"
    discard_pending_console_input()
    clear_screen()
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


def document_files(output_dir: Path) -> list[Path]:
    return sorted(
        (path for path in output_dir.iterdir() if DOCUMENT_PATTERN.fullmatch(path.name)),
        key=lambda path: int(DOCUMENT_PATTERN.fullmatch(path.name).group(1)),
    )


def format_size(size: int) -> str:
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def show_documents(output_dir: Path) -> list[Path]:
    documents = document_files(output_dir)
    print("\nSaved documents:")
    if not documents:
        print("  No saved documents.")
        return documents
    total_size = 0
    total_pages = 0
    for index, path in enumerate(documents, 1):
        size = path.stat().st_size
        total_size += size
        try:
            pages = pdf_page_count(path)
            total_pages += pages
            page_text = f"{pages} page{'s' if pages != 1 else ''}"
        except Exception:
            page_text = "pages unavailable"
        print(f"  {index}. {path.name} | {page_text} | {format_size(size)}")
    print(f"  Total: {len(documents)} documents | {total_pages} pages | {format_size(total_size)}")
    return documents


def render_dashboard(output_dir: Path, document: int, pages: list[Path], dpi: int) -> None:
    clear_screen()
    print(f"{'=' * 42}\n         HP USB Scanner CLI\n{'=' * 42}\n")
    show_documents(output_dir)
    page_count = len(pages)
    page_label = "page" if page_count == 1 else "pages"
    print(f"\nCurrent draft: Document {document:03d} | {page_count} unsaved {page_label}")
    print(f"Scan DPI: {dpi}")


def append_page_to_document(scanner: Scanner, document_path: Path, dpi: int, temp_dir: Path) -> None:
    discard_pending_console_input()
    clear_screen()
    input("Place the page on the scanner, then press ENTER to add it. ")
    temp_path = temp_dir / f"append_{document_path.stem}_{uuid.uuid4().hex}.bmp"
    print(f"\nScanning at {dpi} DPI...")
    appended = False
    try:
        scan_page(scanner, temp_path, dpi)
        append_image_to_pdf(temp_path, document_path)
        appended = True
    except Exception as exc:
        print(f"[ERROR] Could not add page: {exc}")
        if temp_path.exists():
            print(f"Temporary page kept: {temp_path}")
        return
    finally:
        if appended:
            temp_path.unlink(missing_ok=True)
    print(f"[OK] Page added to {document_path.name}")


def manage_documents(scanner: Scanner, output_dir: Path, temp_dir: Path, dpi: int) -> None:
    while True:
        clear_screen()
        documents = show_documents(output_dir)
        if not documents:
            return
        answer = input("\nSelect document number (or b to go back): ").strip().lower()
        if answer in ("b", ""):
            return
        if not answer.isdecimal() or not 1 <= int(answer) <= len(documents):
            print("[ERROR] Enter a listed document number or b.")
            continue
        selected = documents[int(answer) - 1]
        while True:
            clear_screen()
            show_documents(output_dir)
            print(f"\n{selected.name}: [a] Add page  [o] Open  [d] Delete  [b] Back")
            action = input("Enter choice: ").strip().lower()
            if action == "b":
                break
            if action == "a":
                append_page_to_document(scanner, selected, dpi, temp_dir)
            elif action == "o":
                try:
                    os.startfile(selected.resolve())
                except OSError as exc:
                    print(f"[ERROR] Could not open document: {exc}")
            elif action == "d":
                confirm = input(f"Delete {selected.name}? [y/N] ").strip().lower()
                if confirm == "y":
                    try:
                        selected.unlink()
                        print(f"[OK] Deleted {selected.name}")
                    except OSError as exc:
                        print(f"[ERROR] Could not delete document: {exc}")
                    break
            else:
                print("[ERROR] Choose a, o, d, or b.")


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
    clear_screen()
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
    while True:
        command = choose_action(output_dir, document, pages, dpi)
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
                scan_next_page(scanner, document, pages, dpi, temp_dir)
        elif command == "w":
            if save_document(document, pages, output_dir):
                document = next_document_number(output_dir)
        elif command == "r":
            if not pages:
                print("[ERROR] Current draft has no pages to discard.")
                continue
            confirm = input(
                f"[WARNING] Discard {len(pages)} unsaved page(s) from Document {document:03d}? [y/N] "
            ).strip().lower()
            if confirm == "y":
                remove_pages(pages)
                pages.clear()
        elif command == "q":
            if pages and input("[WARNING] Current document has unsaved pages. Quit without saving? [y/N] ").strip().lower() != "y":
                continue
            remove_pages(pages)
            print("Quit.")
            return 0
        elif command == "s":
            dpi = choose_dpi(dpi)
            print(f"[OK] Scan DPI changed to {dpi}. The next page will use this setting.")
        elif command == "m":
            manage_documents(scanner, output_dir, temp_dir, dpi)


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted. Unsaved temporary pages remain in temp/.")
        raise SystemExit(130)
