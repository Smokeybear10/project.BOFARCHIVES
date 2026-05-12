"""Parse the Technology Memos folder into structured data + an HTML page.

The memos follow a template (Executive Summary, Key Facts, Timeline,
References). This pulls out the bits worth showing on the dashboard:
  - technology name
  - RA author
  - executive summary (250-word paragraph)
  - first/last BOF mention
  - domain category

Writes:
  - output/technology_memos.json
  - tech-memos.html (linked from the dashboard sidebar)
"""
from __future__ import annotations

import json
import re
from html import escape as h
from pathlib import Path

from docx import Document
from pypdf import PdfReader

ROOT = Path(__file__).parent
MEMO_DIR = ROOT / "Data" / "Technologies" / "Technology Memos"
OUTPUT = ROOT / "output"


# ── Parsing ────────────────────────────────────────────────────────────────

def _read_docx(path: Path) -> list[str]:
    return [p.text.strip() for p in Document(path).paragraphs]


def _read_pdf(path: Path) -> list[str]:
    """Extract text from a PDF and reflow it into paragraph-like lines.

    Some PDFs in this archive emit one-word-per-line because of how Google Docs
    exports. Re-joining short consecutive lines into one logical line is what
    makes 'Executive Summary' detection work across formats.
    """
    reader = PdfReader(str(path))
    raw_lines: list[str] = []
    for page in reader.pages[:6]:
        text = page.extract_text() or ""
        raw_lines.extend(line.strip() for line in text.split("\n"))
    # Reflow: join short adjacent lines into paragraphs separated by blank rows.
    out: list[str] = []
    buf: list[str] = []
    for line in raw_lines:
        if not line:
            if buf:
                out.append(" ".join(buf))
                buf = []
            continue
        # Single-word or short fragments → keep accumulating
        if len(line) < 60 and not line.endswith((".", "?", "!", ":")):
            buf.append(line)
        else:
            buf.append(line)
            out.append(" ".join(buf))
            buf = []
    if buf:
        out.append(" ".join(buf))
    return out


_NAME_FROM_FILE = re.compile(
    r"(?:Tech\s+Memo[-_\s]*[–-]?\s*|Technology\s+Timeline\s+Memo\s*[–-]\s*"
    r"|Technology\s+timeline\s*[–-]\s*|Technology\s+Timeline\s*[–-]\s*"
    r"|Tech\s+Memo\s*[-_]\s*|\[)",
    flags=re.IGNORECASE,
)


def _tech_name_from_filename(path: Path) -> str:
    stem = path.stem
    # Strip leading "BOF " prefix
    stem = re.sub(r"^BOF\s+", "", stem, flags=re.IGNORECASE)
    # Strip out the template prefixes
    stem = _NAME_FROM_FILE.sub("", stem, count=1)
    # Take up to the author marker (–, -, _, ] followed by an author)
    parts = re.split(r"\s*[\-–_\]]\s*(?=[A-Z][a-z]{2,}\s*$|\[?[A-Za-z]+\]?\s*$)", stem)
    name = parts[0].strip(" -–_[](),")
    # Clean trailing parenthetical author tags like "(Howell Torpedoes)" — keep parenthetical content
    return name


def _author_from_filename(path: Path) -> str:
    stem = path.stem
    # Last name commonly appears after the final dash/dot or in brackets
    m = re.search(r"[-–_]\s*\[?([A-Z][A-Za-z]+)\]?\s*\(?[0-9]?\)?\s*$", stem)
    if m:
        return m.group(1)
    return "—"


def _extract_summary(lines: list[str]) -> str:
    """Find the Executive Summary paragraph."""
    summary_idx = None
    for i, line in enumerate(lines):
        if re.search(r"executive\s+summary", line, re.IGNORECASE):
            summary_idx = i
            break
    if summary_idx is None:
        return ""

    # Collect text after "Executive Summary" until the next numbered section
    # or "Key Facts" heading.
    collected: list[str] = []
    for line in lines[summary_idx + 1: summary_idx + 25]:
        if not line:
            continue
        if re.search(r"^\s*\d+\)\s|key\s+facts|annotated\s+timeline|references",
                     line, re.IGNORECASE):
            break
        # Skip template instruction lines that re-appear in unfilled memos
        if line.startswith("One short paragraph") or "headline timeline" in line.lower():
            continue
        collected.append(line)
        if sum(len(c) for c in collected) > 1400:
            break
    return " ".join(collected).strip()


def _extract_full_body(lines: list[str]) -> list[dict]:
    """Pull out section blocks from a memo: heading + paragraphs.

    Stops at the References / Citations footer. Skips boilerplate template
    instructions present in every memo.
    """
    skip_until: int | None = None
    # Skip the RA-template instruction block at the top
    for i, line in enumerate(lines[:80]):
        if re.search(r"executive\s+summary|key\s+facts|1\)\s", line, re.IGNORECASE):
            skip_until = i
            break
    start = skip_until if skip_until is not None else 0

    sections: list[dict] = []
    current = {"heading": "Body", "lines": []}
    for line in lines[start:]:
        s = line.strip()
        if not s:
            continue
        # Heading detection: numbered like "1) X", "2) X" or text-only "References"
        m = re.match(r"^\s*(\d+\)\s+.+|key\s+facts|annotated\s+timeline|references"
                     r"|outcomes?|sources?\s+used|chicago.style)\s*$", s, re.IGNORECASE)
        if m:
            if current["lines"]:
                sections.append(current)
            heading = re.sub(r"^\s*\d+\)\s*", "", s).strip()
            current = {"heading": heading, "lines": []}
            continue
        # Strip out template hints
        if any(t in s.lower() for t in ("[fill", "make a copy", "annual reports located",
                                         "subjects considered spreadsheets located",
                                         "technology timelines assignment",
                                         "appropriations spreadsheets located",
                                         "instructions for ras")):
            continue
        current["lines"].append(s)
    if current["lines"]:
        sections.append(current)
    return sections


def _extract_field(lines: list[str], label: str) -> str:
    """Find a Key Facts row matching label, return the value."""
    pat = re.compile(rf"^\s*{re.escape(label)}\s*[:|]?\s*(.+)$", re.IGNORECASE)
    for line in lines:
        m = pat.match(line)
        if m:
            val = m.group(1).strip()
            if val and not val.lower().startswith(("[", "fill", "—")):
                return val
    return ""


def parse_memo(path: Path) -> dict | None:
    try:
        if path.suffix.lower() == ".docx":
            lines = _read_docx(path)
        elif path.suffix.lower() == ".pdf":
            lines = _read_pdf(path)
        else:
            return None
    except Exception as e:
        print(f"  WARN {path.name}: {e}")
        return None

    summary = _extract_summary(lines)
    name = _tech_name_from_filename(path)
    # If a clean "Technology:" line exists in the doc, prefer that
    for line in lines[:30]:
        m = re.match(r"^\s*Technology\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            break

    return {
        "tech": name,
        "author": _author_from_filename(path),
        "summary": summary,
        "first_mention": _extract_field(lines, "First BOF mention"),
        "last_mention": _extract_field(lines, "Last BOF mention"),
        "domain": _extract_field(lines, "Domain / category") or _extract_field(lines, "Domain"),
        "inventor": _extract_field(lines, "Inventor(s) / firm(s)") or _extract_field(lines, "Inventor"),
        "body_sections": _extract_full_body(lines),
        "source_file": path.name,
        "format": path.suffix.lstrip(".").lower(),
    }


# ── Build ──────────────────────────────────────────────────────────────────

def collect_memos() -> list[dict]:
    """Walk MEMO_DIR, prefer DOCX over PDF where both exist with the same stem-prefix."""
    files = sorted(MEMO_DIR.glob("*"))
    # Group by tech name (rough): if a DOCX and PDF share the same prefix, take DOCX
    seen_keys: set[str] = set()
    out: list[dict] = []
    # Sort so DOCX comes first when both exist
    docx_files = [f for f in files if f.suffix.lower() == ".docx"]
    pdf_files  = [f for f in files if f.suffix.lower() == ".pdf"]

    for path in docx_files + pdf_files:
        key = re.sub(r"\.(docx|pdf)$", "", path.name, flags=re.IGNORECASE).strip().lower()
        # Drop trailing " (1)" etc. so duplicate pdf/docx are unified
        key_norm = re.sub(r"\s*\(\d+\)\s*$", "", key).strip()
        if key_norm in seen_keys:
            continue
        memo = parse_memo(path)
        if memo and memo["summary"]:
            out.append(memo)
            seen_keys.add(key_norm)
    return out


# ── Render ─────────────────────────────────────────────────────────────────

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Technology Memos · Fortify the Ordnance</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><path fill-rule='evenodd' clip-rule='evenodd' d='M32 3 L42 22 L61 32 L42 42 L32 61 L22 42 L3 32 L22 22 Z M32 26 A6 6 0 1 0 32 38 A6 6 0 1 0 32 26 Z' fill='%23C9A24C'/><circle cx='32' cy='32' r='2.2' fill='%23C9A24C'/></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #F6F6F7;
    --panel: #FFFFFF;
    --panel-2: #FAFAFB;
    --border: #E1E3E6;
    --text: #1A1F36;
    --text-mid: #5A6075;
    --text-soft: #8C92A4;
    --brass: #C9A24C;
    --accent: #635BFF;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', -apple-system, sans-serif;
    font-size: 15.5px;
    line-height: 1.65;
  }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  .topbar {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 28px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; letter-spacing: 1.2px; color: var(--text-mid);
  }}
  .tb-l {{ display: flex; align-items: center; gap: 10px; color: inherit; cursor: pointer; }}
  .tb-l svg {{
    width: 18px; height: 18px; color: var(--brass);
    transition: transform .5s cubic-bezier(.2,.8,.2,1);
  }}
  .tb-l:hover svg {{ transform: rotate(45deg); }}
  .tb-l strong {{ color: var(--text); letter-spacing: 1.4px; }}
  .tb-r a {{ color: var(--text-mid); letter-spacing: 1.2px; }}
  .tb-r a:hover {{ color: var(--brass); text-decoration: none; }}

  .wrap {{
    max-width: 1320px;
    margin: 0 auto;
    padding: 56px 48px 80px;
  }}
  .eyebrow {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px; font-weight: 700; letter-spacing: 2.4px;
    text-transform: uppercase; color: var(--brass);
    margin-bottom: 18px; display: flex; align-items: center; gap: 14px;
  }}
  .eyebrow::before {{ content: ""; width: 32px; height: 1px; background: var(--brass); }}
  h1 {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-weight: 700; font-size: 52px; letter-spacing: -1.4px;
    line-height: 1.04; margin-bottom: 18px; max-width: 1040px;
  }}
  h1 em {{ font-style: italic; color: var(--brass); font-weight: 400; }}
  .lede {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 19px; line-height: 1.5; color: var(--text-mid);
    max-width: 920px; margin-bottom: 14px;
  }}
  .stats {{
    display: flex; gap: 14px; margin: 28px 0 36px; flex-wrap: wrap;
  }}
  .stat {{
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 6px; padding: 14px 18px; min-width: 120px;
  }}
  .stat .n {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 22px; font-weight: 700; letter-spacing: -0.3px;
  }}
  .stat .l {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9.5px; letter-spacing: 1.4px;
    text-transform: uppercase; color: var(--text-soft);
    margin-top: 5px; font-weight: 600;
  }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
    gap: 16px;
  }}
  .memo {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 22px 24px;
    display: flex; flex-direction: column; gap: 8px;
    transition: border-color .15s, box-shadow .15s;
    cursor: pointer;
  }}
  .memo:hover {{
    border-color: var(--brass);
    box-shadow: 0 4px 14px rgba(60, 40, 10, .08);
  }}
  .memo .name {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 19px; font-weight: 700; line-height: 1.25;
  }}
  .memo .meta {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px; letter-spacing: 0.8px;
    text-transform: uppercase; color: var(--text-soft);
    display: flex; gap: 12px; flex-wrap: wrap;
  }}
  .memo .meta b {{ color: var(--text-mid); font-weight: 700; }}
  .memo .summary {{
    color: var(--text-mid);
    font-size: 14.5px;
    line-height: 1.55;
    flex: 1;
  }}
  .memo .facts {{
    display: flex; gap: 18px; flex-wrap: wrap;
    margin-top: 4px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
    font-size: 12.5px;
    color: var(--text-mid);
  }}
  .memo .facts span b {{ color: var(--text); font-weight: 600; }}
  .memo .read-more {{
    margin-top: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px; letter-spacing: 1px;
    text-transform: uppercase; color: var(--brass); font-weight: 700;
  }}

  /* Detail modal — opens on card click, shows the full memo body */
  .modal-bg {{
    position: fixed; inset: 0;
    background: rgba(15, 23, 42, 0.55);
    display: none;
    align-items: flex-start; justify-content: center;
    padding: 56px 24px;
    z-index: 1000;
    overflow-y: auto;
  }}
  .modal-bg.open {{ display: flex; }}
  .modal {{
    background: var(--panel);
    border-radius: 10px;
    max-width: 920px; width: 100%;
    padding: 36px 44px 44px;
    box-shadow: 0 16px 60px rgba(0, 0, 0, 0.22);
    position: relative;
    font-family: 'Source Serif 4', Georgia, serif;
  }}
  .modal-close {{
    position: absolute; top: 14px; right: 16px;
    background: transparent; border: 0; cursor: pointer;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; letter-spacing: 1px;
    color: var(--text-mid); padding: 6px 10px;
    border-radius: 4px;
  }}
  .modal-close:hover {{ color: var(--brass); background: var(--panel-2); }}
  .modal h2 {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 32px; font-weight: 700; letter-spacing: -0.6px;
    line-height: 1.1; margin-bottom: 6px;
  }}
  .modal .modal-meta {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px; letter-spacing: 1px;
    text-transform: uppercase; color: var(--text-soft);
    margin-bottom: 24px;
    padding-bottom: 18px;
    border-bottom: 1px solid var(--border);
  }}
  .modal h3 {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 17px; font-weight: 700;
    margin: 24px 0 10px;
    color: var(--text);
  }}
  .modal p {{
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 16px; line-height: 1.65;
    color: var(--text); margin-bottom: 12px;
  }}
  .modal a {{ color: var(--accent); }}
  .modal-source {{
    margin-top: 26px; padding-top: 18px;
    border-top: 1px solid var(--border);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; color: var(--text-soft); letter-spacing: 0.6px;
  }}

  footer {{
    margin-top: 64px; padding-top: 22px;
    border-top: 1px solid var(--border);
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: var(--text-soft); letter-spacing: 1px;
    display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px;
  }}
  footer a {{ color: var(--text-mid); }}

  @media (max-width: 720px) {{
    .wrap {{ padding: 36px 20px 56px; }}
    h1 {{ font-size: 36px; letter-spacing: -1px; }}
    .grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="topbar">
  <a class="tb-l" href="/" title="Back to dashboard">
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <path fill-rule="evenodd" clip-rule="evenodd" d="M32 3 L42 22 L61 32 L42 42 L32 61 L22 42 L3 32 L22 22 Z M32 26 A6 6 0 1 0 32 38 A6 6 0 1 0 32 26 Z" fill="currentColor"/>
      <circle cx="32" cy="32" r="2.2" fill="currentColor"/>
    </svg>
    <strong>FORTIFY THE ORDNANCE</strong>
  </a>
  <div class="tb-r"><a href="/">← back to dashboard</a></div>
</div>
<div class="wrap">
  <div class="eyebrow">Technology memos</div>
  <h1>The case files <em>behind</em> the technologies</h1>
  <p class="lede">
    Detailed write-ups of the BOF-reviewed technologies — one memo per device, produced
    by RAs from the original Board reports and contemporary sources. Each card is the
    executive summary plus first / last BOF mention.
  </p>
  <div class="stats">
    <div class="stat"><div class="n">{n_memos}</div><div class="l">Memos</div></div>
    <div class="stat"><div class="n">{n_authors}</div><div class="l">RAs</div></div>
    <div class="stat"><div class="n">{n_docx}</div><div class="l">DOCX</div></div>
    <div class="stat"><div class="n">{n_pdf}</div><div class="l">PDF</div></div>
  </div>
  <div class="grid">
    {cards}
  </div>
</div>
<div class="modal-bg" id="modal-bg" role="dialog" aria-modal="true">
  <div class="modal" id="modal-body">
    <button class="modal-close" id="modal-close" aria-label="Close">× close</button>
  </div>
</div>
<footer>
  <span>Built from Data/Technologies/Technology Memos/ · re-parse with <code>python build_tech_memos.py</code></span>
  <a href="https://github.com/Smokeybear10/104-RSCH.BOFARCHIVES" target="_blank" rel="noopener">github ↗</a>
</footer>
<script>
  const memos = {memos_json};
  const bg = document.getElementById('modal-bg');
  const body = document.getElementById('modal-body');
  const closeBtn = document.getElementById('modal-close');

  function openMemo(idx) {{
    const m = memos[idx];
    if (!m) return;
    const facts = [];
    if (m.first_mention) facts.push('<b>First BOF mention:</b> ' + m.first_mention);
    if (m.last_mention)  facts.push('<b>Last BOF mention:</b> ' + m.last_mention);
    if (m.domain)        facts.push('<b>Domain:</b> ' + m.domain);
    if (m.inventor)      facts.push('<b>Inventor:</b> ' + m.inventor);
    const sections = (m.body_sections || []).map(s =>
      '<h3>' + escapeHtml(s.heading) + '</h3>' +
      s.lines.map(l => '<p>' + escapeHtml(l) + '</p>').join('')
    ).join('');
    body.innerHTML =
      '<button class="modal-close" id="modal-close-x" aria-label="Close">× close</button>' +
      '<h2>' + escapeHtml(m.tech) + '</h2>' +
      '<div class="modal-meta">RA ' + escapeHtml(m.author) + ' · ' + m.format.toUpperCase() +
      (facts.length ? ' · ' + facts.join(' · ') : '') + '</div>' +
      sections +
      '<div class="modal-source">Source file: <code>Data/Technologies/Technology Memos/' +
      escapeHtml(m.source_file) + '</code></div>';
    bg.classList.add('open');
    document.getElementById('modal-close-x').addEventListener('click', closeMemo);
    document.body.style.overflow = 'hidden';
  }}
  function closeMemo() {{
    bg.classList.remove('open');
    document.body.style.overflow = '';
  }}
  function escapeHtml(s) {{
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }}
  document.querySelectorAll('.memo').forEach((el, i) => {{
    el.addEventListener('click', () => openMemo(i));
    el.tabIndex = 0;
    el.addEventListener('keydown', e => {{
      if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); openMemo(i); }}
    }});
  }});
  bg.addEventListener('click', e => {{ if (e.target === bg) closeMemo(); }});
  closeBtn.addEventListener('click', closeMemo);
  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeMemo(); }});
</script>
</body>
</html>"""


def _card(memo: dict) -> str:
    summary = memo["summary"][:600]
    if len(memo["summary"]) > 600:
        summary += "…"
    facts: list[str] = []
    if memo["first_mention"]:
        facts.append(f'<span><b>First mention:</b> {h(memo["first_mention"][:80])}</span>')
    if memo["last_mention"]:
        facts.append(f'<span><b>Last mention:</b> {h(memo["last_mention"][:80])}</span>')
    if memo["domain"]:
        facts.append(f'<span><b>Domain:</b> {h(memo["domain"][:60])}</span>')
    return (
        f'<div class="memo" role="button">'
        f'<div class="name">{h(memo["tech"])}</div>'
        f'<div class="meta"><b>RA</b> {h(memo["author"])} <b>·</b> {memo["format"].upper()}</div>'
        f'<div class="summary">{h(summary)}</div>'
        + (f'<div class="facts">{"".join(facts)}</div>' if facts else "")
        + '<div class="read-more">Read full memo →</div>'
        + '</div>'
    )


def main() -> None:
    print(f"Walking {MEMO_DIR}…")
    memos = collect_memos()
    print(f"  parsed {len(memos)} memos")

    # Sort by tech name
    memos.sort(key=lambda m: m["tech"].lower())

    # Write JSON
    json_path = OUTPUT / "technology_memos.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(memos, indent=2), encoding="utf-8")
    print(f"  → {json_path}")

    # Render HTML
    cards = "\n".join(_card(m) for m in memos)
    # Inline the memo data so the page is fully self-contained (no fetch needed)
    memos_json = json.dumps(memos).replace("</", "<\\/")
    page = _PAGE.format(
        n_memos=len(memos),
        n_authors=len({m["author"] for m in memos if m["author"] != "—"}),
        n_docx=sum(1 for m in memos if m["format"] == "docx"),
        n_pdf=sum(1 for m in memos if m["format"] == "pdf"),
        cards=cards,
        memos_json=memos_json,
    )
    out = ROOT / "tech-memos.html"
    out.write_text(page, encoding="utf-8")
    print(f"  → {out}")


if __name__ == "__main__":
    main()
