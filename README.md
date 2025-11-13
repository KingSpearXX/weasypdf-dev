## PDF Generator Demo

### Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Run the API server

```bash
source .venv/bin/activate
uvicorn api:app --reload
```

Create a job:

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
        "template": "greeting",
        "data_source": "data/default.json",
        "context": {
          "recipient": "Product Team",
          "metadata": {
            "report_id": "INV-2042",
            "owner": "Alice"
          }
        }
      }'
```

Poll for status (returns `queued`, `completed`, or `failed`):

```bash
curl http://localhost:8000/jobs/<job_id>
```

Generated PDFs are stored in the `output/` directory using the job id as the filename.

-   `template` maps to a folder under `templates/`.
-   `data_source` (optional) is resolved relative to that folder, letting you pick any JSON preset such as `data/customer-42.json`.
-   `context` is an arbitrary object merged last, so you can pass IDs, names, item overrides, or `parameters` that your template’s JSON/remote fetch placeholders reference.

### Template structure

Templates live under `templates/<name>/` so each design is fully self-contained. Example:

```
templates/
  greeting/
    template.html   # Jinja template
    style.css       # WeasyPrint-compatible CSS
    data/
      default.json  # baseline context values
    assets/
      logo.png
    fonts/
      DejaVuSans.ttf
```

`render_pdf` takes the folder name (e.g., `greeting`). Relative links inside the HTML/CSS resolve against that folder, so you can bundle images, fonts, and partials without touching global paths.

### Pre-resolving context data

Place JSON files under the template directory (e.g., `templates/greeting/data/default.json`) to define the variables passed to Jinja. When you call `render_pdf`, the loader automatically merges:

1. `data/default.json` (or `data.json` if present)
2. Any additional JSON you reference via `data_source="data/another.json"`
3. Ad-hoc overrides passed through the `context` argument

Merging is recursive, so providing a partial object (e.g., only `{"parameters": {"team_limit": 1}}`) overrides just those nested fields without wiping the rest of the structure.

Example:

```python
render_pdf(
    template_name="greeting",
    output_name="invoice.pdf",
    data_source="data/week-42.json",
    context={"recipient": "Product Team"}  # overrides the JSON value
)
```

### Remote data fetch instructions

Any JSON file can declare a `"__remote__"` array to fetch external payloads before rendering. Each instruction supports:

```json
{
    "__remote__": [
        {
            "url": "https://example.com/items.json",
            "target": "items",
            "mode": "replace",
            "headers": {"Authorization": "Bearer <token>"},
            "timeout": 15,
            "enabled": true
        }
    ]
}
```

-   `target` defines where the fetched JSON lands (dot notation allowed, omit to merge at root).
-   `mode` accepts `replace` (default) or `extend` to append list payloads instead of replacing.
-   `enabled=false` lets you keep fetch definitions versioned without triggering them locally.
-   Strings such as `url` and header values support `{path.to.value}` placeholders that are resolved against the merged context (e.g., `{parameters.user_id}`).

If the fetch fails, `render_pdf` raises an error explaining which URL was unreachable, so your API/UI can report it back to the user.
