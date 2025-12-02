# General Session Log

## Repository Overview
- **Purpose:** Generate styled PDFs from HTML templates resolved with SAP data via configurable data maps. Includes a minimal FastAPI stub for testing.
- **Key Entry Points:**
  - `pdf-gen.py` – CLI utility that renders `templates/<slug>/template.html` with a resolved context and writes the PDF via WeasyPrint.
  - `pdf-api.py` – FastAPI sample exposing `/test/{name}` and `/greet` endpoints, demonstrating how the rendering utilities could be surfaced as services.

## Directory Layout
| Path | Contents |
| --- | --- |
| `helpers.py` | Helper utilities (currently `format_iso_date`) for template consumption. |
| `pdf-gen.py` | Rendering workflow (context resolution, Jinja environment, PDF output). |
| `resolver.py` | DataMapResolver implementation (fetch handling, interpolation, transform support, plugin hooks). |
| `plugins/` | Auto-discovered plugin modules (e.g., `doc_rows.get_doc_rows`). |
| `templates/` | Individual template packages (`sample`, `sales-quotation`) containing HTML, CSS, data maps, assets, and fonts. |
| `output/` | Destination for generated PDFs. |
| `requirements.txt` | Runtime dependencies (Jinja2, WeasyPrint, FastAPI, Uvicorn). |

## Rendering Pipeline
1. **Context Resolution (`pdf-gen.py:14-47`):**
   - Loads `templates/<slug>/data/datamap.json`.
   - Uses `DataMapResolver` to merge fetched data with optional seed context.
2. **Template Rendering (`pdf-gen.py:49-61`):**
   - Creates a Jinja2 environment rooted at the template directory.
   - Renders `template.html` with the resolved context (ensure helpers are injected, e.g., `resolved_context["helpers"] = helpers` after import).
3. **PDF Generation (`pdf-gen.py:63-74`):**
   - Loads `style.css` if present.
   - Invokes `weasyprint.HTML(...).write_pdf` with `base_url` set to the template directory so relative assets resolve correctly.
4. **Output:** PDFs land in `output/<name>.pdf`.

## Data Map & Resolver Mechanics
- **Interpolation:** Strings can include `{Placeholder}` expressions resolved from the growing state dictionary.
- **Fetch Blocks:** `{"fetch": { ... }}` definitions support HTTP GET/POST with headers, params, body, defaults, and optional transforms (`json`/`text`/`bytes`). Responses can be assigned back into the state via `target` or `id`.
- **Sequences:** Ordered actions (`fetch`, `assign`, `plugin`) executed with intermediate storage via `id`.
- **Transforms:** Built-in modifiers (`uppercase`, `lowercase`, `json`) applied post-resolution (`resolver.py:227-244`).
- **Plugins:** Registered callables inside `plugins/` (auto-loaded via `plugins/__init__.py`). Example: `doc_rows.get_doc_rows` merges SAP document line collections; data maps can invoke it using `{"sequence": [{"action": "plugin", "name": "doc_rows", ...}]}`.
- **New Plugin (`plugins/search_item.py`):** `find_item(items, key=..., value=...)` scans an iterable of mappings and returns the first entry whose `key` equals `value` (supports strict match and stringified fallback). Registered as `find_item` for use inside data-map plugin steps. Typical usage inside a datamap:
  ```json
  {
    "action": "plugin",
    "name": "find_item",
    "args": [
      { "ref": "fetchBPData.ContactEmployees" }
    ],
    "kwargs": {
      "key": "InternalCode",
      "value": "{fetchQuoteData.ContactPersonCode}"
    },
    "id": "ContactPersonData"
  }
  ```
  The resolver resolves the `ref` to the contact list, interpolates the `value`, and stores the matching object (or `null`) under `ContactPersonData`.

## Recent Context
- Added `helpers.py` with `format_iso_date` to format SAP timestamps before rendering.
- `datamap.json` for sales quotations now chains multiple fetches, inserts a `delay` action between them, and uses the `find_item` plugin to resolve `ContactPersonData`.
- The `doc_rows` plugin output is exposed via `DocumentRowsData`, and `row-lines.html` now loops over that collection to render each line dynamically, including optional lead-time copy.
- Debugging tips: run scripts through VS Code’s `Python Debugger: Current File with Arguments` launch config to hit breakpoints; remember to open the target file before pressing F5.

## Helper Utilities
- `helpers.py` currently exposes `format_iso_date`, which normalizes ISO 8601 strings (including trailing `Z`) to `mm/dd/yyyy` via `datetime`. Import the module (`import helpers`) and pass it into template context for Jinja usage (`helpers.format_iso_date(...)`).

## Template Packages
- **Structure (e.g., `templates/sales-quotation/`):**
  - `template.html` – Top-level skeleton includes partials (`partials/*.html`).
  - `css/` – `layout.css` imports `global.css` to define CSS variables and embeds fonts via `@font-face` pointing at `../fonts/*.woff2`.
  - `partials/` – Header/footer/rows, referencing context keys (`QuoteData.*`).
  - `data/datamap.json` – Defines data sources (currently a single fetch to `/api/sap/Quotations({DocEntry})`).
  - `fonts/`, `assets/` – Static resources consumed during rendering.
- **Sample Template (`templates/sample/`):** Demonstrates basic `@font-face`, inline styles, and example data files.

## API Stub
- `pdf-api.py` is a placeholder FastAPI app with:
  - `GET /test/{name}` – Echoes `name` and optional `DocEntry`.
  - `POST /greet` – Returns greeting using Pydantic model validation.
  - Can be extended to wrap the `render_pdf` function for HTTP-based generation.

## Dependencies & Tooling
- Python runtime (3.11+ recommended for type hints like `|`).
- `requirements.txt` ensures compatible versions:
  - Jinja2 3.1.x for templating.
  - WeasyPrint 62.x for HTML-to-PDF rendering (requires Cairo, Pango, etc., at the system level).
  - FastAPI/Uvicorn for serving APIs (optional).

## Operational Notes
- Fonts referenced in CSS use paths relative to the CSS file—no project-root prefix required.
- Helper functions must be explicitly imported and injected into the template context.
- Resolver transforms are limited; extend `_apply_transform` or use plugins/helpers for complex formatting (e.g., date parsing).
- Keep `output/` writable; script creates the directory automatically.

## Next Steps / TODOs
1. Wrap `render_pdf` with FastAPI endpoints (e.g., `/pdf/{template}`) using `pdf-api.py`.
2. Expand resolver transforms to include date formatting or numeric formatting if recurring needs arise.
3. Document plugin usage in template-specific README files.
4. Automate nightly logs: append to this file post-build describing changes, tests run, and assets generated.
