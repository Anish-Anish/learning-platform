"""Deterministic parsing of uploaded material into page Markdown.

PDF: text with heading detection, tables as Markdown, embedded images and vector figures rendered to PNG
(described later by the vision model), and scanned pages rendered for OCR. Markdown / plain text pass through.
Figures are left in the text as `[[FIGURE:<id>]]` markers so descriptions land where the figure was.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_SUFFIXES = {".pdf", ".md", ".markdown", ".txt"}

MAX_RENDER_PX = 1024
OCR_RENDER_PX = 1600
MAX_FIGURES_KEPT = 300
MIN_FIGURE_PT = 72  # one inch on the page


class ParseError(ValueError):
    pass


@dataclass
class Figure:
    id: str
    page: int
    kind: str  # "image" | "drawing" | "scan"
    png: bytes
    area: float


@dataclass
class ParsedPage:
    number: int
    markdown: str
    scanned: bool = False


@dataclass
class ParsedDocument:
    doc_id: str
    filename: str
    pages: list[ParsedPage]
    figures: list[Figure] = field(default_factory=list)
    page_count: int = 0
    stats: dict = field(default_factory=dict)

    @property
    def chars(self) -> int:
        return sum(len(p.markdown) for p in self.pages)


def parse_file(path: Path, doc_id: str, filename: str, max_pages: int, min_image_px: int) -> ParsedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ParseError(f"unsupported file type {suffix or '(none)'}; use PDF, Markdown or text")
    if suffix == ".pdf":
        return parse_pdf(path, doc_id, filename, max_pages, min_image_px)
    text = path.read_bytes().decode("utf-8", errors="replace")
    return ParsedDocument(doc_id=doc_id, filename=filename, pages=[ParsedPage(1, text.strip())], page_count=1,
                          stats={"pages": 1, "chars": len(text), "tables": 0, "figures": 0, "scanned_pages": 0})


# ------------------------------------------------------------------ PDF
def _overlap(a, b) -> float:
    """Share of rect a covered by rect b."""
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    area = (a[2] - a[0]) * (a[3] - a[1])
    return ((x1 - x0) * (y1 - y0)) / area if area > 0 else 0.0


def _body_font_size(doc, n_pages: int) -> float:
    sizes: Counter[float] = Counter()
    step = max(1, n_pages // 40)
    for i in range(0, n_pages, step):
        for block in doc[i].get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sizes[round(span.get("size", 0), 1)] += len(span.get("text", "").strip())
    return sizes.most_common(1)[0][0] if sizes else 11.0


def heading_level(size: float, body: float, bold: bool, text: str) -> int:
    """0 = body text. Pure so it can be unit-tested."""
    t = text.strip()
    if not t or len(t) > 120 or t.endswith((".", ",", ";")) or body <= 0:
        return 0
    if size >= body * 1.6:
        return 1
    if size >= body * 1.25:
        return 2
    if bold and size >= body * 1.05 and len(t) < 80:
        return 3
    return 0


def _render(page, rect, max_px: int) -> bytes:
    import pymupdf

    zoom = max(0.5, min(3.0, max_px / max(rect.width, rect.height, 1)))
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect, alpha=False).tobytes("png")


def parse_pdf(path: Path, doc_id: str, filename: str, max_pages: int, min_image_px: int) -> ParsedDocument:
    import pymupdf

    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise ParseError(f"could not open PDF: {exc}") from exc
    if doc.needs_pass:
        raise ParseError("PDF is password-protected")
    n = min(doc.page_count, max_pages)
    body = _body_font_size(doc, n)
    pages: list[ParsedPage] = []
    figures: list[Figure] = []
    seen_xrefs: set[int] = set()
    seen_hashes: set[str] = set()
    stats = Counter(tables=0, figures=0, scanned_pages=0, figures_skipped=0, table_errors=0)

    def keep_figure(fig_id: str, page_no: int, kind: str, png: bytes, area: float) -> bool:
        sha = hashlib.sha1(png).hexdigest()
        if sha in seen_hashes:
            return False
        seen_hashes.add(sha)
        if len(figures) >= MAX_FIGURES_KEPT:
            stats["figures_skipped"] += 1
            return False
        figures.append(Figure(fig_id, page_no, kind, png, area))
        stats["figures"] += 1
        return True

    for i in range(n):
        page = doc[i]
        page_no = i + 1
        prect = page.rect
        items: list[tuple[float, float, str]] = []  # (y, x, markdown)

        tables = []
        try:
            for t in page.find_tables().tables:
                md = t.to_markdown(clean=False).strip()
                if md:
                    tables.append(tuple(t.bbox))
                    items.append((t.bbox[1], t.bbox[0], md))
                    stats["tables"] += 1
        except Exception:
            stats["table_errors"] += 1

        text_chars = 0
        for block in page.get_text("dict", sort=True).get("blocks", []):
            if block.get("type") != 0:
                continue
            bbox = tuple(block["bbox"])
            if any(_overlap(bbox, tb) > 0.5 for tb in tables):
                continue
            lines_md: list[str] = []
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in line["spans"]).strip()
                size = max(s.get("size", 0) for s in spans)
                bold = all(s.get("flags", 0) & 16 for s in spans)
                lvl = heading_level(size, body, bold, text)
                lines_md.append(f"{'#' * lvl} {text}" if lvl else text)
                text_chars += len(text)
            if lines_md:
                items.append((bbox[1], bbox[0], _join_lines(lines_md)))

        image_area = 0.0
        for k, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            for rect in rects[:1]:
                rect = rect & prect
                if rect.is_empty:
                    continue
                image_area += rect.width * rect.height
                if xref in seen_xrefs:  # logos / headers repeated on every page
                    continue
                if rect.width < MIN_FIGURE_PT or rect.height < MIN_FIGURE_PT:
                    continue
                if min(img[2], img[3]) < min_image_px:
                    continue
                seen_xrefs.add(xref)
                fig_id = f"{doc_id}_p{page_no}_i{k}"
                if keep_figure(fig_id, page_no, "image", _render(page, rect, MAX_RENDER_PX), rect.width * rect.height):
                    items.append((rect.y0, rect.x0, f"[[FIGURE:{fig_id}]]"))

        try:
            clusters = page.cluster_drawings()
        except Exception:
            clusters = []
        big = [r for r in clusters
               if r.width >= prect.width * 0.25 and r.height >= prect.height * 0.12
               and not any(_overlap(tuple(r), tb) > 0.5 for tb in tables)]
        for k, rect in enumerate(big[:2]):
            fig_id = f"{doc_id}_p{page_no}_d{k}"
            if keep_figure(fig_id, page_no, "drawing", _render(page, rect, MAX_RENDER_PX), rect.width * rect.height):
                items.append((rect.y0, rect.x0, f"[[FIGURE:{fig_id}]]"))

        scanned = text_chars < 50 and image_area >= 0.4 * prect.width * prect.height
        if scanned:
            stats["scanned_pages"] += 1
            figures[:] = [f for f in figures if f.page != page_no]  # the whole-page OCR covers them
            fig_id = f"{doc_id}_p{page_no}_scan"
            figures.append(Figure(fig_id, page_no, "scan", _render(page, prect, OCR_RENDER_PX), prect.width * prect.height))
            items = [(0.0, 0.0, f"[[FIGURE:{fig_id}]]")]

        items.sort(key=lambda t: (round(t[0], 0), t[1]))
        pages.append(ParsedPage(page_no, "\n\n".join(md for _, _, md in items).strip(), scanned))

    total_pages = doc.page_count
    doc.close()
    out_stats = {"pages": n, "pages_total": total_pages, "truncated_pages": max(0, total_pages - n),
                 "chars": sum(len(p.markdown) for p in pages), "body_font_size": body, **dict(stats)}
    return ParsedDocument(doc_id=doc_id, filename=filename, pages=pages, figures=figures, page_count=total_pages,
                          stats=out_stats)


def _join_lines(lines: list[str]) -> str:
    """Headings on their own line; consecutive body lines joined into a paragraph (de-hyphenated)."""
    out: list[str] = []
    para = ""
    for ln in lines:
        if ln.startswith("#"):
            if para:
                out.append(para)
                para = ""
            out.append(ln)
            continue
        if para.endswith("-") and not para.endswith(" -"):
            para = para[:-1] + ln
        else:
            para = f"{para} {ln}".strip()
    if para:
        out.append(para)
    return "\n\n".join(out)
