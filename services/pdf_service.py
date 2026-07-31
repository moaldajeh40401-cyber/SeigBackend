from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT_DIR / "generated_pdfs"


def ensure_generated_dir() -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    return GENERATED_DIR


def is_managed_pdf_path(path: str | Path) -> bool:
    try:
        Path(path).resolve().relative_to(GENERATED_DIR.resolve())
        return True
    except ValueError:
        return False


def delete_managed_pdf(path: str | Path) -> None:
    candidate = Path(path)
    if is_managed_pdf_path(candidate) and candidate.exists():
        candidate.unlink()


def build_resume_pdf_bytes(html: str) -> bytes:
    """Render the same Jinja HTML/CSS used by preview into an ATS-safe PDF."""
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as error:
        raise RuntimeError(
            "WeasyPrint requires its native GTK/Pango libraries. Install them on Windows "
            "or run the backend in Linux/Docker."
        ) from error
    return HTML(string=html, base_url=str(ROOT_DIR)).write_pdf()
