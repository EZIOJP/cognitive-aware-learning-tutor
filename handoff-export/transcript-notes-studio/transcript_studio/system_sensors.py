"""Best-effort CPU temperature and load — Windows-first, no required extras."""

from __future__ import annotations

import re
import subprocess
import sys


def try_cpu_temp_celsius() -> float | None:
    """Return CPU-ish temperature in °C, or None if sensors are unavailable."""
    for reader in (_temp_powershell_acpi, _temp_wmi, _temp_psutil):
        try:
            value = reader()
        except Exception:
            value = None
        if value is not None and 10.0 <= value <= 110.0:
            return value
    return None


def try_cpu_load_pct() -> float | None:
    """Recent CPU utilization 0–100, or None."""
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Processor).LoadPercentage",
                ],
                stderr=subprocess.DEVNULL,
                timeout=8,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    return float(line)
        except Exception:
            pass
    try:
        import psutil  # type: ignore

        return float(psutil.cpu_percent(interval=0.3))
    except Exception:
        return None


def format_system_line(*, temp_c: float | None = None, load_pct: float | None = None) -> str:
    parts: list[str] = []
    if temp_c is not None:
        parts.append(f"CPU {temp_c:.0f}°C")
    else:
        parts.append("CPU temp n/a")
    if load_pct is not None:
        parts.append(f"load {load_pct:.0f}%")
    return " · ".join(parts)


def _temp_powershell_acpi() -> float | None:
    if sys.platform != "win32":
        return None
    script = (
        "Get-CimInstance -Namespace root/WMI -ClassName MSAcpi_ThermalZoneTemperature "
        "| Select-Object -First 1 -ExpandProperty CurrentTemperature"
    )
    out = subprocess.check_output(
        ["powershell", "-NoProfile", "-Command", script],
        stderr=subprocess.DEVNULL,
        timeout=10,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).strip()
    if not out:
        return None
    raw = float(re.search(r"[\d.]+", out).group(0))  # type: ignore[union-attr]
    return (raw / 10.0) - 273.15


def _temp_wmi() -> float | None:
    if sys.platform != "win32":
        return None
    import wmi  # type: ignore

    acpi = wmi.WMI(namespace="root\\wmi")
    readings = acpi.MSAcpi_ThermalZoneTemperature()
    if not readings:
        return None
    raw = float(readings[0].CurrentTemperature)
    return (raw / 10.0) - 273.15


def _temp_psutil() -> float | None:
    import psutil  # type: ignore

    temps = getattr(psutil, "sensors_temperatures", lambda: {})()
    if not temps:
        return None
    for key in ("coretemp", "cpu_thermal", "k10temp", "acpitz"):
        if key in temps and temps[key]:
            return float(temps[key][0].current)
    first = next(iter(temps.values()), None)
    if first:
        return float(first[0].current)
    return None
