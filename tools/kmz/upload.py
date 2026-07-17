"""Upload built KMZ files to the Spain 2026 Drive folder.

Upserts by name: if a KMZ of the same name already lives in the target folder,
its contents are replaced in place (stable file id and share URL, so a My Maps
re-import points at the same file) rather than creating a duplicate.
"""

from pathlib import Path

from mgdio.drive import list_files, update_file, upload_file

# "kmz" folder inside the shared Spain 2026 Drive folder.
KMZ_FOLDER_ID = "1my9-4BKx0luCOUPZ1nzaHxa9fJDv7Kl_"
KMZ_MIME_TYPE = "application/vnd.google-earth.kmz"


def upload_kmz(
    path: Path,
    *,
    folder_id: str = KMZ_FOLDER_ID,
    profile: str | None = None,
) -> tuple[str, str, bool]:
    """Upload one KMZ, replacing any same-named file in the folder.

    Args:
        path: Local ``.kmz`` file to upload.
        folder_id: Destination Drive folder id.
        profile: Optional mgdio Google profile slug.

    Returns:
        A tuple of (file name, web view link, updated_in_place). The bool is
        True when an existing file was replaced, False when a new file was
        created.
    """
    kwargs = {"profile": profile} if profile else {}
    name = path.name
    existing = list_files(
        query=f"name = '{name}' and trashed = false",
        parent_id=folder_id,
        **kwargs,
    )
    if existing:
        drive_file = update_file(existing[0].id, local_path=str(path), **kwargs)
        return drive_file.name, drive_file.web_view_link, True

    drive_file = upload_file(
        str(path),
        name=name,
        parent_id=folder_id,
        mime_type=KMZ_MIME_TYPE,
        **kwargs,
    )
    return drive_file.name, drive_file.web_view_link, False
