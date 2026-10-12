#!/usr/bin/env python3
"""
Bulk PDF text extractor for the brain-alpha-pipeline research corpus.
Extracts raw text from each PDF in docs/research/ and writes to
docs/kb/extracted_text/<filename_stem>.txt for use during KB file creation.

Usage:
    python scripts/extract_pdf_text.py
    python scripts/extract_pdf_text.py --file Xing_Zhang_Zhao_Volatility_Smirk.pdf
    python scripts/extract_pdf_text.py --file Xing_Zhang_Zhao_Volatility_Smirk.pdf --pages 5
"""
import argparse
import os
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF not found. Run: pip install pymupdf")

RESEARCH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "research")
OUTPUT_DIR   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "kb", "extracted_text")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def extract_pdf(pdf_path: str, max_pages: int = 0, max_chars: int = 80000) -> str:
    """Extract text from a PDF, up to max_chars characters."""
    doc = fitz.open(pdf_path)
    pages = doc.page_count if max_pages == 0 else min(max_pages, doc.page_count)
    chunks = []
    total = 0
    for i in range(pages):
        page_text = doc[i].get_text("text")
        chunks.append(f"\n--- PAGE {i+1} ---\n{page_text}")
        total += len(page_text)
        if total >= max_chars:
            chunks.append(f"\n[TRUNCATED at {max_chars} chars — {doc.page_count} total pages]\n")
            break
    doc.close()
    return "".join(chunks)


def process_one(filename: str, max_pages: int = 0):
    src = os.path.join(RESEARCH_DIR, filename)
    if not os.path.exists(src):
        print(f"NOT FOUND: {src}")
        return
    stem = os.path.splitext(filename)[0]
    out  = os.path.join(OUTPUT_DIR, f"{stem}.txt")
    if os.path.exists(out):
        print(f"SKIP (already extracted): {stem}")
        return
    print(f"Extracting: {filename} ...", end=" ", flush=True)
    text = extract_pdf(src, max_pages=max_pages)
    with open(out, "w", encoding="utf-8", errors="replace") as f:
        f.write(text)
    size_kb = os.path.getsize(out) // 1024
    print(f"done ({size_kb} KB)")


def main():
    parser = argparse.ArgumentParser(description="Extract PDF text from research corpus")
    parser.add_argument("--file",  help="Single PDF filename to extract (just the filename, not full path)")
    parser.add_argument("--pages", type=int, default=0, help="Max pages to extract (0 = all)")
    parser.add_argument("--all",   action="store_true", help="Extract all PDFs in research dir")
    args = parser.parse_args()

    if args.file:
        process_one(args.file, max_pages=args.pages)
    elif args.all:
        pdfs = sorted([f for f in os.listdir(RESEARCH_DIR) if f.lower().endswith(".pdf")])
        print(f"Found {len(pdfs)} PDFs. Extracting all...")
        for pdf in pdfs:
            process_one(pdf, max_pages=args.pages)
        print(f"\nAll done. Extracted text in: {OUTPUT_DIR}")
    else:
        # Default: extract all
        pdfs = sorted([f for f in os.listdir(RESEARCH_DIR) if f.lower().endswith(".pdf")])
        print(f"Found {len(pdfs)} PDFs. Extracting all...")
        for pdf in pdfs:
            process_one(pdf)
        print(f"\nAll done. Output dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
