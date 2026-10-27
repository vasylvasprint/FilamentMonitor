"""GCode and 3MF file parser for filament usage extraction.

Supports OrcaSlicer, PrusaSlicer, Cura, Bambu Studio comment formats.
Also handles .3mf (ZIP) files containing gcode inside.
"""
import re
import zipfile
import io
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Slicer comment patterns for filament weight ──────────────────────────────
_PATTERNS = [
    # OrcaSlicer / PrusaSlicer / Bambu Studio
    re.compile(r";\s*filament\s+used\s*\[g\]\s*=\s*([\d.]+)", re.IGNORECASE),
    # Cura (filament_amount in grams)
    re.compile(r";\s*Filament\s+used\s*:\s*([\d.]+)\s*g", re.IGNORECASE),
    # Cura material_amount
    re.compile(r";\s*material_amount\s*=\s*([\d.]+)", re.IGNORECASE),
    # Simplify3D
    re.compile(r";\s*Plastic\s+weight\s*=\s*([\d.]+)\s*g", re.IGNORECASE),
    # Generic weight comment
    re.compile(r";\s*(?:weight|wt|mass)\s*[=:]\s*([\d.]+)\s*g", re.IGNORECASE),
    # IdeaMaker
    re.compile(r";\s*Filament\s+consumption\s*=\s*([\d.]+)\s*g", re.IGNORECASE),
]

# Multiple filament pattern (OrcaSlicer multi-material)
_MULTI_PATTERN = re.compile(
    r";\s*filament\s+used\s*\[g\]\s*=\s*([\d.,\s]+)",
    re.IGNORECASE,
)

# Slicer detection
_SLICER_PATTERNS = {
    "OrcaSlicer": re.compile(r";\s*generated\s+by\s+OrcaSlicer", re.IGNORECASE),
    "PrusaSlicer": re.compile(r";\s*generated\s+by\s+PrusaSlicer", re.IGNORECASE),
    "Bambu Studio": re.compile(r";\s*generated\s+by\s+Bambu\s+Studio", re.IGNORECASE),
    "Cura": re.compile(r";\s*Generated\s+with\s+Cura", re.IGNORECASE),
    "Simplify3D": re.compile(r";\s*Simplify3D", re.IGNORECASE),
    "IdeaMaker": re.compile(r";\s*IdeaMaker", re.IGNORECASE),
}


def detect_slicer(gcode_text: str) -> str:
    """Detect which slicer generated this GCode."""
    for name, pattern in _SLICER_PATTERNS.items():
        if pattern.search(gcode_text):
            return name
    return "Unknown"


def parse_gcode_text(gcode_text: str) -> Tuple[Optional[float], str]:
    """
    Parse gcode text for filament usage.
    Returns (grams, slicer_name).
    For multi-material, returns the sum.
    """
    slicer = detect_slicer(gcode_text)

    # Try multi-filament first (OrcaSlicer: "filament used [g] = 10.5, 0, 5.2")
    multi_match = _MULTI_PATTERN.search(gcode_text)
    if multi_match:
        values_str = multi_match.group(1)
        values = [float(v.strip()) for v in re.split(r"[,\s]+", values_str) if v.strip()]
        if values:
            total = sum(values)
            return round(total, 2), slicer

    # Single filament patterns
    for pattern in _PATTERNS:
        match = pattern.search(gcode_text)
        if match:
            return round(float(match.group(1)), 2), slicer

    return None, slicer


def parse_gcode_file(file_bytes: bytes, filename: str) -> Tuple[Optional[float], str, Optional[str]]:
    """
    Parse a .gcode or .3mf file for filament usage.
    Returns (grams, slicer_name, error_message).
    """
    filename_lower = filename.lower()

    if filename_lower.endswith(".3mf"):
        return _parse_3mf(file_bytes, filename)
    elif filename_lower.endswith(".gcode") or filename_lower.endswith(".bgcode"):
        try:
            # Try UTF-8, fall back to latin-1
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = file_bytes.decode("latin-1", errors="replace")
            grams, slicer = parse_gcode_text(text)
            if grams is None:
                return None, slicer, "Не вдалося знайти дані про витрату філаменту в файлі"
            return grams, slicer, None
        except Exception as e:
            return None, "Unknown", f"Помилка читання файлу: {e}"
    else:
        return None, "Unknown", f"Непідтримуваний тип файлу: {filename}"


def _parse_3mf(file_bytes: bytes, filename: str) -> Tuple[Optional[float], str, Optional[str]]:
    """Parse a .3mf (ZIP) file for filament usage."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            names = zf.namelist()
            logger.debug(f"3MF contents: {names}")

            # Try common gcode locations inside .3mf
            gcode_candidates = [
                n for n in names
                if n.endswith(".gcode") or "Metadata/plate" in n or "model.gcode" in n
            ]

            for candidate in gcode_candidates:
                try:
                    gcode_bytes = zf.read(candidate)
                    try:
                        text = gcode_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        text = gcode_bytes.decode("latin-1", errors="replace")
                    grams, slicer = parse_gcode_text(text)
                    if grams is not None:
                        return grams, slicer, None
                except Exception as e:
                    logger.debug(f"Error reading {candidate} from 3MF: {e}")

            # Try slice_info.config (Bambu Studio)
            config_candidates = [n for n in names if "slice_info" in n or "config" in n.lower()]
            for candidate in config_candidates:
                try:
                    config_bytes = zf.read(candidate)
                    text = config_bytes.decode("utf-8", errors="replace")
                    # Look for filament_used or similar
                    match = re.search(r"filament_used.*?=\s*([\d.]+)", text, re.IGNORECASE)
                    if match:
                        return round(float(match.group(1)), 2), "Bambu Studio", None
                except Exception:
                    pass

            return None, "Unknown", "Не вдалося знайти дані про витрату в .3mf файлі"
    except zipfile.BadZipFile:
        return None, "Unknown", "Файл .3mf пошкоджений або не є ZIP-архівом"
    except Exception as e:
        return None, "Unknown", f"Помилка обробки .3mf: {e}"
