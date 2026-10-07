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

At startup, choose `150` or `300` at the DPI prompt; pressing Enter keeps the 300 DPI default. You can change this later with `[s]`, and the new resolution applies to the next page and later pages. A single PDF can contain pages scanned at different resolutions.

The app then asks whether to create a folder for the session. Press Enter to keep using the standard `scans` and `temp` folders. Choose `y` and enter a name to store PDFs in `scanner-cli\scans\<session-name>` and temporary BMP pages in its `temp` subfolder. An existing session folder is reused, and numbering continues after its highest numbered PDF.

Place a page on the flatbed and press Enter when prompted. The app sets the chosen DPI horizontally and vertically before every scan. If the driver rejects either setting, the scan fails with an error instead of using another DPI. After each scan:

| Command | Action |
| --- | --- |
| `n` | Scan another page into the current document; after a failed scan, retry the same page. |
| `d` | Save the current document as a PDF and immediately start the next document. |
| `x` | Save the current document as a PDF and exit. |
| `q` | Quit without saving the current document; asks for confirmation if it has pages. |
| `s` | Change between 150 and 300 DPI for subsequent pages. |

PDFs are named `document_001.pdf`, `document_002.pdf`, and so on. The next number is one greater than the highest existing numbered PDF in the active output folder. Existing PDFs are never overwritten. Temporary BMP pages are removed after a successful save or confirmed `q`. If a PDF save fails, the temporary pages remain available for a retry. If the process is interrupted, temporary files remain for manual inspection; move or remove stale files before retrying the same document number. After `[x]` successfully saves the document, the active output folder opens in Windows Explorer.

## Scanner behavior and limits

The app uses WIA's first scan item and requests one BMP image per transfer. It sets only the horizontal and vertical resolution to the selected DPI; color mode and other settings remain at driver defaults. WIA feature support varies by driver and USB setup. This MVP assumes pages are placed manually on the flatbed and does not control the automatic document feeder. Verify the selected resolution with a physical scan.
