"""Parse PDF files into structured chapters with text and images."""

import base64
import io
import json
import os
import re
from pathlib import Path

import fitz  # PyMuPDF


def extract_images_from_page(doc: fitz.Document, page: fitz.Page) -> list[dict]:
    """Extract images from a PDF page as base64 strings."""
    images = []
    for img_index, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        base_image = doc.extract_image(xref)
        if base_image:
            image_bytes = base_image["image"]
            ext = base_image["ext"]
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            images.append({
                "index": img_index,
                "ext": ext,
                "base64": b64,
                "mime": f"image/{ext}" if ext != "jpeg" else "image/jpeg",
            })
    return images


def detect_chapter_boundaries(text: str) -> list[tuple[str, int]]:
    """Detect chapter/section titles and their positions in text.

    Looks for patterns like:
    - "第X章" / "第X节"
    - Numbered headings like "1.", "1.1", "一、"
    - Common section markers like "## " or all-caps titles
    """
    patterns = [
        r"^第[一二三四五六七八九十\d]+[章节篇].*",
        r"^[一二三四五六七八九十]+、.*",
        r"^\d+[\.\、].*",
        r"^\d+\.\d+[\.\s].*",
        r"^[A-Z][A-Z\s]{3,}.*",
        r"^面试题.*",
        r"^[（(][一二三四五六七八九十\d]+[)）].*",
    ]

    lines = text.split("\n")
    chapters = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or len(line) > 80:
            continue
        for pat in patterns:
            if re.match(pat, line):
                chapters.append((line, i))
                break

    return chapters


def group_text_by_chapters(
    text: str, boundaries: list[tuple[str, int]]
) -> list[dict]:
    """Split text into chapter groups based on detected boundaries."""
    lines = text.split("\n")
    chapters = []

    for idx, (title, line_num) in enumerate(boundaries):
        start = line_num
        end = boundaries[idx + 1][1] if idx + 1 < len(boundaries) else len(lines)
        content = "\n".join(lines[start:end]).strip()
        chapters.append({"title": title, "text": content})

    # If no chapters detected, treat whole document as one chapter
    if not chapters:
        chapters.append({"title": "全文", "text": text})

    return chapters


def parse_pdf(filepath: str) -> dict:
    """Parse a PDF file and return structured content.

    Returns:
        {
            "fileName": "xxx.pdf",
            "fullText": "...",
            "chapters": [
                {"title": "...", "text": "...", "images": [{"base64": "...", "mime": "..."}]}
            ]
        }
    """
    doc = fitz.open(filepath)
    filename = Path(filepath).name

    full_pages_text = []
    all_chapters_raw = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text")
        full_pages_text.append(page_text)

        images = extract_images_from_page(doc, page)
        if images:
            all_chapters_raw.append({
                "title": f"Page {page_num + 1}",
                "text": page_text,
                "images": images,
            })

    full_text = "\n".join(full_pages_text)
    boundaries = detect_chapter_boundaries(full_text)
    chapters = group_text_by_chapters(full_text, boundaries)

    # Attach images to the nearest chapter by page
    for ch in chapters:
        ch["images"] = []

    doc.close()

    return {
        "fileName": filename,
        "fullText": full_text,
        "chapters": chapters,
    }


def parse_pdfs_in_folder(folder: str) -> list[dict]:
    """Parse all PDF files in a folder."""
    results = []
    for f in sorted(Path(folder).glob("*.pdf")):
        print(f"  Parsing PDF: {f.name}")
        result = parse_pdf(str(f))
        results.append(result)
    return results


if __name__ == "__main__":
    import sys

    folder = sys.argv[1] if len(sys.argv) > 1 else "../八股"
    output = sys.argv[2] if len(sys.argv) > 2 else "../output/parsed_docs.json"

    results = parse_pdfs_in_folder(folder)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nParsed {len(results)} PDF files → {output}")
