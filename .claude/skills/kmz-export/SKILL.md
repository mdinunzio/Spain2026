---
name: kmz-export
description: >
  Build KMZ files for Google My Maps from the Spain 2026 Locations data,
  natively (no mapitquick.com). Use this when the user wants to generate a
  map, export the Locations tab to KMZ/My Maps, refresh the map after editing
  venues, produce per-region or per-type map layers, or turn emoji into custom
  map pins. Renders emoji pins deterministically from Twemoji and packages
  doc.kml + icons/ into a KMZ that imports cleanly into My Maps.
---

# KMZ Export

Convert the Spain 2026 **Locations** into KMZ file(s) for Google My Maps. This
replaces mapitquick.com, which chokes on the Locations CSV export.

## What it does

1. Loads venues from the live **Locations** tab (default) or the formatted
   batch JSON under `parsed/formatted/`.
2. Renders each venue's emoji to a PNG pin via **Twemoji** (72×72), cached in
   `.twemoji-cache/` so repeat runs are offline.
3. Writes a rich My Maps info-popup description (rating, type, neighborhood,
   cost, address, clickable Google Maps + References links, tags). Venues with
   the **Selected** box checked show a ✅ marker, and any **Notes** are shown
   as "📝 Our notes" at the top of the popup. Both come from the sheet, or from
   `parsed/annotations.json` when building with `--source json`.
4. Packages `doc.kml` + `icons/` into a `.kmz` (the layout My Maps expects).

## Usage

Run from the repo root (`c:\Users\mdinu\Code\Spain2026`) with the project venv:

```bash
# Single combined layer from the live Locations tab (default)
.venv/Scripts/python.exe -m tools.kmz.build

# One KMZ per region (import each as its own My Maps layer)
.venv/Scripts/python.exe -m tools.kmz.build --split-by region

# One KMZ per venue type
.venv/Scripts/python.exe -m tools.kmz.build --split-by type

# Split the committed picks (Selected column) from the candidates
.venv/Scripts/python.exe -m tools.kmz.build --split-by selected

# Build from the formatted batch JSON instead of the sheet
.venv/Scripts/python.exe -m tools.kmz.build --source json

# Build and upload the result to the Spain 2026 Drive "kmz" folder
.venv/Scripts/python.exe -m tools.kmz.build --upload
```

Options:

- `--source {sheet,json}` — read the live Locations tab (default) or
  `parsed/formatted/*.json`. The sheet reflects manual edits; JSON carries the
  original provenance URLs and approximate-location notes.
- `--split-by {none,region,type,selected}` — `none` (default) is one file /
  one layer. `region` or `type` emit one file per group. `selected` emits a
  `spain2026_selected.kmz` (the venues with the Selected box checked) and a
  `spain2026_candidates.kmz` (everything else), so you can keep the committed
  list as its own always-on My Maps layer.
- `--out DIR` — output directory (default `parsed/kmz`).
- `--cache-dir DIR` — emoji PNG cache (default `.twemoji-cache`).
- `--upload` — after building, upload each KMZ to the Spain 2026 Drive `kmz`
  folder (`tools/kmz/upload.py`, `KMZ_FOLDER_ID`). Upserts by filename, so a
  re-run replaces the file in place and its Drive URL / My Maps import stays
  stable instead of spawning duplicates.
- `--profile SLUG` — mgdio Google profile, when `--source sheet`.

## Importing into My Maps

1. Open the map at [google.com/mymaps](https://www.google.com/mymaps).
2. On a layer, click **Import** and choose the `.kmz`.
3. For split output, use **Add layer → Import** once per file.

Note the My Maps limits: **10 layers/map, 2,000 features/layer, 10,000/map**.
`--split-by type` can exceed 10 groups; the CLI warns when it does.

## Safety

- **Read-only against the sheet.** The `sheet` source only *reads* the
  Locations tab; it never writes. No confirmation needed.
- **Network on first run.** Emoji PNGs are fetched from the Twemoji CDN once,
  then cached. Warm the cache online before an offline session.

## Idiosyncrasies handled (so My Maps behaves)

- `doc.kml` must be the archive root member; icons live in `icons/` and are
  referenced by **relative** href — that is what makes My Maps use custom pins.
- Emoji can't be pins directly, so each is baked into a PNG. Twemoji (not the
  OS font) keeps pins identical on every machine and reproducible run to run.
- The U+FE0F variation selector is stripped from Twemoji filenames except in
  keycap sequences; ZWJ sequences (e.g. 👩‍🍳) keep all codepoints.
- Descriptions use only My Maps-supported HTML (`<b>`, `<br>`, `<i>`,
  `<a href>`), escaped once (apostrophes left literal — `&apos;` is invalid
  HTML and would show literally).
- Coordinates are emitted **longitude,latitude,altitude** (KML order).

## Code

- `tools/kmz/build.py` — CLI entry point (`python -m tools.kmz.build`).
- `tools/kmz/sources.py` — load from sheet / JSON; URL reconstruction.
- `tools/kmz/emoji.py` — Twemoji filename derivation + fetch/cache.
- `tools/kmz/descriptions.py` — info-popup HTML.
- `tools/kmz/kml.py` — KML document/placemark builder.
- `tools/kmz/package.py` — KMZ zip assembly.
- `tests/test_kmz.py` — unit tests for the above (`pytest tests/test_kmz.py`).
