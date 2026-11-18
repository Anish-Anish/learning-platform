"""Split parsed documents into LLM-sized chunks, preferring heading boundaries and keeping page references."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.ai.ingest.parse import ParsedDocument


@dataclass
class Chunk:
    index: int
    filename: str
    page_start: int
    page_end: int
    text: str

    @property
    def ref(self) -> str:
        pages = f"p. {self.page_start}" if self.page_start == self.page_end else f"pp. {self.page_start}-{self.page_end}"
        return f"{self.filename}, {pages}"


def chunk_size_for(total_chars: int, base: int, max_chunks: int) -> int:
    """Grow the chunk size for very large inputs so the number of map calls stays bounded."""
    return max(base, math.ceil(total_chars / max_chunks)) if total_chars else base


class _Builder:
    def __init__(self, filename: str, out: list[Chunk]) -> None:
        self.filename, self.out = filename, out
        self.buf: list[str] = []
        self.size = 0
        self.start = self.end = 0

    def add(self, para: str, page: int) -> None:
        if not self.buf:
            self.start = page
        self.buf.append(para)
        self.size += len(para) + 2
        self.end = page

    def flush(self) -> None:
        text = "\n\n".join(self.buf).strip()
        if text:
            self.out.append(Chunk(len(self.out), self.filename, self.start, self.end, text))
        self.buf, self.size = [], 0


def chunk_documents(docs: list[ParsedDocument], base_chars: int, max_chunks: int) -> list[Chunk]:
    size = chunk_size_for(sum(d.chars for d in docs), base_chars, max_chunks)
    chunks: list[Chunk] = []
    for d in docs:
        b = _Builder(d.filename, chunks)
        for page in d.pages:
            for para in page.markdown.split("\n\n"):
                para = para.strip()
                if not para:
                    continue
                soft_break = para.startswith("#") and b.size >= size * 0.5
                if b.buf and (b.size + len(para) > size or soft_break):
                    b.flush()
                while len(para) > size:  # a single enormous paragraph / table
                    b.add(para[:size], page.number)
                    b.flush()
                    para = para[size:]
                b.add(para, page.number)
        b.flush()
    return chunks
