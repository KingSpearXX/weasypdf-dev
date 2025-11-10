from pathlib import Path
from typing import Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import CSS, HTML

BASE_DIR = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"
STYLE_DIR = BASE_DIR / "styles"


def render_pdf(
    template_name: str,
    context: dict,
    output_name: str,
    stylesheets: Iterable[Path] | None = None,
) -> Path:
    """
    Render the given Jinja template with context and turn it into a PDF.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(template_name)
    html = template.render(**context)

    css_objects = (
        [CSS(filename=str(css_path)) for css_path in stylesheets]
        if stylesheets
        else None
    )

    output_path = OUTPUT_DIR / output_name
    HTML(string=html, base_url=str(BASE_DIR)).write_pdf(
        output_path, stylesheets=css_objects
    )
    return output_path


if __name__ == "__main__":
    pdf_path = render_pdf(
        template_name="greeting.html",
        context={
            "title": "WeasyPrint + Jinja demo",
            "recipient": "Codex User",
            "items": [
                {"name": "Feature work", "hours": 3, "rate": 120},
                {"name": "Debugging", "hours": 1.5, "rate": 140},
            ],
        },
        output_name="sample.pdf",
        stylesheets=[STYLE_DIR / "report.css"],
    )
    print(f"PDF saved to {pdf_path}")
