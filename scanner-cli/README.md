# Scanner CLI

A small Windows terminal app that scans one page at a time from a USB scanner and combines the pages of each document into a numbered PDF. It uses Windows Image Acquisition (WIA) for scanning and `img2pdf` for PDF creation. It does not use HP Smart, network scanning, OCR, or image processing.

## Requirements

- Windows 10 or 11
- Python 3.12 recommended
- A scanner connected by USB, with a working WIA driver
- For the HP LaserJet Pro MFP M428dw, install the HP USB scanner driver if Windows has not already installed one. A printer-only driver is insufficient.

The application accepts only WIA scanner entries whose `Port` starts with `\\.\Usbscan`. Network, WSD, and eSCL network entries are excluded. The M428/M429 USB WIA driver tested here reports `\\.\Usbscan0` and supports BMP transfer.

## Install

The existing virtual environment is in the parent project folder. If it is already installed, skip this step. Otherwise, open PowerShell in the parent folder (`HP Scan CLI Tool`):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scanner-cli\requirements.txt
```

## Launch

Double-click `scan.bat` in the parent folder. It runs `scanner-cli\main.py` with the existing parent `.venv` and pauses before closing so you can read the result.

For a manual PowerShell launch from `scanner-cli`:

```powershell
..\.venv\Scripts\python.exe main.py
```

To test detection without scanning, run this from `scanner-cli`:

```powershell
..\.venv\Scripts\python.exe main.py --list-scanners
```

It should print the USB scanner name and port, then exit. On the development PC it printed `HP LJ Pro M428M429 (USB) (\\.\Usbscan0)`.

If no device appears, check the USB cable and power, then open **Device Manager > Imaging devices** (or **Cameras**) and look for the USB scanner. You can also open the Windows **Scan** app to see whether Windows can acquire an image from the USB device. If Windows sees only a network scanner or a printer, install or repair the HP USB scan driver, reconnect the USB cable, and retry detection. The Windows Image Acquisition (WIA) service must be running.

## Scan documents

At startup, choose a DPI using the numbered prompt:

```text
Scan DPI
[1] 300
[2] 150
Enter choice:
```

Pressing Enter keeps the current DPI. You can change this later with `[s]` or `[*]`, and the new resolution applies to the next page and later pages. A single PDF can contain pages scanned at different resolutions.

The app then asks whether to create a folder for the session. Press Enter to keep using the standard `scans` and `temp` folders. Choose `y` and enter a name to store PDFs in `scanner-cli\scans\<session-name>` and temporary BMP pages in its `temp` subfolder. An existing session folder is reused, and numbering continues after its highest numbered PDF.

The dashboard lists saved PDFs in the active output folder, including each PDF's page count and size plus overall totals. It also shows the current unsaved draft. Use `n` to place and scan the first page; the app sets the chosen DPI horizontally and vertically before every scan. If the driver rejects either setting, the scan fails with an error instead of using another DPI. Commands are:

| Command | Action |
| --- | --- |
| `n` or `1` | Scan the next page in the current document. This is the default when the draft has no pages. |
| `d` or `2` | Finish the current document, save it, and start a new one. This is the default when the draft has pages. |
| `x` or `3` | Finish the current document, save it, and exit. |
| `q` or `4` | Quit without saving the current document; asks for confirmation if it has pages. |
| `s` or `*` | Change between 150 and 300 DPI for subsequent pages. |
| `w` | Save the current document and return to an empty next draft without scanning. |
| `r` | Discard the current unsaved pages after confirmation. |
| `m` | List saved documents in the current output folder, including each PDF's page count and file size plus overall totals. You can add a page, open a PDF, or delete a PDF. |

PDFs are named `document_001.pdf`, `document_002.pdf`, and so on. The next number is one greater than the highest existing numbered PDF in the active output folder. Existing PDFs are never overwritten. Temporary BMP pages are removed after a successful save or confirmed `q`. If a PDF save fails, the temporary pages remain available for a retry. If the process is interrupted, temporary files remain for manual inspection; move or remove stale files before retrying the same document number. After `[x]` successfully saves the document, an empty session `temp` folder is removed and the active output folder opens in Windows Explorer. The shared `scanner-cli\temp` folder remains in place when no named session is used.

The app clears the console before the dashboard, page prompt, DPI prompt, and document manager so prior command history does not accumulate. It also clears queued key presses before the dashboard and before every page prompt. Wait until the prompt appears before pressing Enter. In the action menu, Enter deliberately selects `[d]` when the current draft has pages, or `[n]` when it does not. The document manager works only with documents in the active output folder. Adding a page updates the selected PDF; deleting a document asks for confirmation.

## Scanner behavior and limits

The app uses WIA's first scan item and requests one BMP image per transfer. It sets only the horizontal and vertical resolution to the selected DPI; color mode and other settings remain at driver defaults. WIA feature support varies by driver and USB setup. This MVP assumes pages are placed manually on the flatbed and does not control the automatic document feeder. Verify the selected resolution with a physical scan.
