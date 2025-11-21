import sys
from pathlib import Path
from typing import Mapping

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import CSS, HTML

from resolver import DataMapResolver, resolve_data_map_file

BASE_DIR = Path(__file__).parent
TEMPLATE_ROOT = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"

def resolve_context(
    template_slug: str,
    datamap_name: str = "data/datamap.json",
    seed_context: Mapping | None = None,
) -> dict:
    """Resolve the datamap under templates/<slug>/ using DataMapResolver."""
    resolver = DataMapResolver()
    datamap_path = TEMPLATE_ROOT / template_slug / datamap_name
    if not datamap_path.exists():
        raise FileNotFoundError(f"Datamap not found: {datamap_path}")
    resolved = resolve_data_map_file(
        datamap_path,
        seed_context=seed_context,
        resolver=resolver,
    )
    if seed_context:
        merged = dict(seed_context)
        merged.update(resolved)
        return merged
    return resolved

def render_pdf(
    template_slug: str,
    context: Mapping,
    output_name: str,
) -> Path:
    """Render templates/<slug>/template.html using the resolved context."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    template_dir = TEMPLATE_ROOT / template_slug

    resolved_context = resolve_context(
        template_slug,
        seed_context=context,
    )

    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )
    try:
        template = env.get_template('template.html')
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to load template 'template.html'") from exc

    try:
        html = template.render(**resolved_context)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Failed to render template with provided context") from exc

    css_path = template_dir / "style.css"
    stylesheets = [CSS(filename=str(css_path))] if css_path.exists() else None

    output_path = OUTPUT_DIR / output_name
    try:
        HTML(string=html, base_url=str(template_dir)).write_pdf(
            output_path,
            stylesheets=stylesheets,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to write PDF to '{output_path}'") from exc
    return output_path


if __name__ == "__main__":
    TEMPLATE_SLUG = "sales-quotation"
    SEED_CONTEXT = {
        "DocNum": 2332091,
    }
    try:
        pdf_path = render_pdf(
            template_slug=TEMPLATE_SLUG,
            context=SEED_CONTEXT,
            output_name=f"{TEMPLATE_SLUG}-test.pdf",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error generating PDF: {exc}")
        sys.exit(1)
    else:
        print(f"PDF saved to {pdf_path}")
