"""USB-only scanner access through Windows Image Acquisition (WIA)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


BMP_FORMAT = "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}"
SCANNER_DEVICE_TYPE = 1
SCAN_DPI = 300
WIA_IPS_XRES = 6147
WIA_IPS_YRES = 6148


class ScannerError(Exception):
    """A scanner could not be found, connected to, or used."""


@dataclass(frozen=True)
class Scanner:
    name: str
    device_id: str
    port: str


def _wia_manager():
    if sys.platform != "win32":
        raise ScannerError("This application requires Windows.")
    try:
        from win32com.client import Dispatch

        return Dispatch("WIA.DeviceManager")
    except Exception as exc:
        raise ScannerError(f"Could not open Windows WIA: {exc}") from exc


def _property(properties, name: str) -> str:
    try:
        return str(properties.Item(name).Value)
    except Exception:
        return ""


def _set_scan_resolution(properties, dpi: int) -> None:
    for property_id, axis in ((WIA_IPS_XRES, "horizontal"), (WIA_IPS_YRES, "vertical")):
        try:
            setting = next(
                (prop for prop in properties if int(prop.PropertyID) == property_id),
                None,
            )
            if setting is None:
                raise ValueError(f"WIA property {property_id} is unavailable")
            setting.Value = dpi
            if int(setting.Value) != dpi:
                raise ValueError(f"driver returned {setting.Value} DPI")
        except Exception as exc:
            raise ScannerError(f"Could not set {axis} resolution to {dpi} DPI: {exc}") from exc


def list_scanners() -> list[Scanner]:
    """Return only WIA scanner entries with a verified USB scan port."""
    try:
        devices = _wia_manager().DeviceInfos
        found = []
        for info in devices:
            if int(info.Type) != SCANNER_DEVICE_TYPE:
                continue
            port = _property(info.Properties, "Port")
            if not port.lower().startswith("\\\\.\\usbscan"):
                continue
            found.append(
                Scanner(
                    name=_property(info.Properties, "Name") or "Unnamed USB scanner",
                    device_id=str(info.DeviceID),
                    port=port,
                )
            )
        return found
    except ScannerError:
        raise
    except Exception as exc:
        raise ScannerError(f"Could not list WIA scanners: {exc}") from exc


def scan_page(scanner: Scanner, output_path: Path, dpi: int = SCAN_DPI) -> Path:
    """Acquire one flatbed page and save it as a BMP file."""
    if dpi not in (150, 300):
        raise ValueError("Scan DPI must be 150 or 300")
    if output_path.suffix.lower() != ".bmp":
        raise ValueError("Temporary scan path must end in .bmp")
    if output_path.exists():
        raise ScannerError(f"Temporary scan already exists: {output_path}. Move or remove it before retrying")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        manager = _wia_manager()
        info = manager.DeviceInfos.Item(scanner.device_id)
        device = info.Connect()
        if device.Items.Count < 1:
            raise ScannerError("The scanner has no WIA scan item.")
        item = device.Items.Item(1)
        _set_scan_resolution(item.Properties, dpi)
        image = item.Transfer(BMP_FORMAT)
        if str(image.FormatID).upper() != BMP_FORMAT:
            raise ScannerError("The scanner did not return BMP data.")
        image.SaveFile(str(output_path.resolve()))
        if output_path.stat().st_size == 0:
            raise ScannerError("The scanner returned an empty image.")
        return output_path
    except ScannerError:
        output_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        raise ScannerError(f"Scan failed: {exc}") from exc
