"""Assemble a .kmz archive from KML plus emoji icon PNGs.

A KMZ is a ZIP whose main document must be named ``doc.kml`` at the root,
with asset files (here, pin PNGs) in a subfolder referenced by relative href.
"""

import zipfile
from pathlib import Path

from tools.kmz.kml import ICON_DIR


def write_kmz(
    out_path: Path,
    kml: str,
    icons: dict[str, tuple[str, bytes]],
) -> Path:
    """Write a KMZ archive to disk.

    Args:
        out_path: Destination ``.kmz`` path (parent dirs are created).
        kml: The KML document text; stored as ``doc.kml`` at the archive root.
        icons: Mapping of emoji -> (filename, PNG bytes); stored under
            ``icons/``. Only the filename and bytes are used.

    Returns:
        The path written.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written_names: set[str] = set()
    with zipfile.ZipFile(
        out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive.writestr("doc.kml", kml)
        for filename, data in icons.values():
            # Distinct emojis map to distinct filenames, but guard anyway so a
            # collision can never write the same archive member twice.
            if filename in written_names:
                continue
            archive.writestr(f"{ICON_DIR}/{filename}", data)
            written_names.add(filename)
    return out_path
