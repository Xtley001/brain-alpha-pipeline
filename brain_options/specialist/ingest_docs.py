"""
Automated Document & Literature Ingestion Utility for Options Alpha Pipeline.
Reads PDF, TXT, EPUB, and MD files from docs/research/ and extracts text content
ready for quantitative card synthesis and knowledge base expansion.
"""
import os
import sys
from pathlib import Path


def extract_text_from_file(file_path: str) -> str:
    """Extracts raw text from PDF, TXT, MD, or other text formats."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in [".txt", ".md", ".json", ".csv"]:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    elif suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            text_pages = []
            for i, page in enumerate(reader.pages):
                extracted = page.extract_text() or ""
                text_pages.append(f"--- [Page {i+1}] ---\n{extracted}")
            return "\n\n".join(text_pages)
        except Exception as e:
            return f"Error reading PDF: {e}"

    else:
        return f"Unsupported file type: {suffix}"


def scan_research_dir(research_dir: str = "docs/research") -> list[dict]:
    """Scans the research directory and returns metadata of available documents."""
    p = Path(research_dir)
    if not p.exists():
        return []
    
    docs = []
    for f in p.iterdir():
        if f.is_file() and f.name != "README.md":
            docs.append({
                "name": f.name,
                "path": str(f.resolve()),
                "size_kb": round(f.stat().st_size / 1024, 2),
                "extension": f.suffix.lower()
            })
    return docs


if __name__ == "__main__":
    docs = scan_research_dir()
    print(f"Found {len(docs)} documents in docs/research/:")
    for d in docs:
        print(f" - {d['name']} ({d['size_kb']} KB)")
