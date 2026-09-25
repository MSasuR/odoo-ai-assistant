"""Markdown chunking by headings, with a maximum size and overlap.

Each chunk keeps its heading path ("Runbook > 4. Procedure > Step 2"), which is
prepended to the text before embedding: it greatly improves retrieval of short sections
that would not say what they are about on their own.
"""
import re
from dataclasses import dataclass

MAX_CHARS = 1200
OVERLAP = 150
_HEADING = re.compile(r"^(#{1,4})\s+(.*\S)\s*$")


@dataclass
class Chunk:
    source: str
    heading: str
    content: str

    @property
    def text_for_embedding(self) -> str:
        return f"{self.heading}\n\n{self.content}" if self.heading else self.content


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split a long block by paragraphs; a paragraph above the limit is cut with a sliding window."""
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    buf = ""
    for para in re.split(r"\n\s*\n", text):
        if len(para) > max_chars:
            if buf:
                parts.append(buf)
                buf = ""
            step = max_chars - overlap
            parts += [para[i : i + max_chars] for i in range(0, len(para), step)]
        elif len(buf) + len(para) + 2 <= max_chars:
            buf = f"{buf}\n\n{para}" if buf else para
        else:
            parts.append(buf)
            # overlap: carry the tail of the previous block so context is not cut
            buf = f"{buf[-overlap:]}\n\n{para}" if overlap and buf else para
    if buf:
        parts.append(buf)
    return [p.strip() for p in parts if p.strip()]


def chunk_markdown(text: str, source: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[Chunk]:
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, list[str]]] = [("", [])]
    in_code = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        m = None if in_code else _HEADING.match(line)
        if m:
            level, title = len(m.group(1)), m.group(2)
            stack = [(lv, t) for lv, t in stack if lv < level] + [(level, title)]
            sections.append((" > ".join(t for _, t in stack), []))
        else:
            sections[-1][1].append(line)

    chunks: list[Chunk] = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if len(body) < 20:  # headings without content of their own
            continue
        for piece in _split_long(body, max_chars, overlap):
            chunks.append(Chunk(source=source, heading=heading, content=piece))
    return chunks
