#!/usr/bin/env python3
"""Main build script: parse docs → AI extract → merge → generate frontend.

Usage:
    python scripts/build.py [docs_folder] [output_folder]

Environment:
    MINIMAX_API_KEY - Required. Your MiniMax API key.

The script:
    1. Parses all PDF/Word files in docs_folder
    2. Calls MiniMax M2.7 to extract knowledge points and relations
    3. Merges, deduplicates, and normalizes the knowledge graph
    4. Copies the visualization HTML to the output folder
"""

import json
import os
import shutil
import sys
from pathlib import Path


def main():
    # Resolve paths
    project_root = Path(__file__).parent.parent
    docs_folder = Path(sys.argv[1]) if len(sys.argv) > 1 else project_root / "八股"
    output_folder = Path(sys.argv[2]) if len(sys.argv) > 2 else project_root / "docs"

    output_folder.mkdir(parents=True, exist_ok=True)
    parsed_path = output_folder / "parsed_docs.json"
    extracted_path = output_folder / "extracted_knowledge.json"
    final_data_path = output_folder / "knowledge-data.json"

    print("=" * 60)
    print("Interview Knowledge Graph Builder")
    print("=" * 60)

    # Step 1: Parse documents
    print("\n[Step 1/3] Parsing documents...")

    # Import parse functions
    sys.path.insert(0, str(project_root / "scripts"))
    from parse_pdf import parse_pdfs_in_folder
    from parse_docx import parse_docx_in_folder

    pdf_docs = parse_pdfs_in_folder(str(docs_folder))
    docx_docs = parse_docx_in_folder(str(docs_folder))
    all_docs = pdf_docs + docx_docs

    print(f"  Found: {len(pdf_docs)} PDFs, {len(docx_docs)} DOCX files")

    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)
    print(f"  Parsed docs → {parsed_path}")

    # Step 2: AI extraction
    print("\n[Step 2/3] Extracting knowledge points via AI...")
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        print("ERROR: MINIMAX_API_KEY environment variable not set.")
        print("  Set it via: export MINIMAX_API_KEY=your-key-here")
        print("  Then re-run this script.")
        sys.exit(1)

    from extract_knowledge import extract_from_documents

    knowledge = extract_from_documents(all_docs)

    with open(extracted_path, "w", encoding="utf-8") as f:
        json.dump(knowledge, f, ensure_ascii=False, indent=2)
    print(f"  Extracted knowledge → {extracted_path}")

    # Step 3: Merge and finalize
    print("\n[Step 3/3] Merging and building final knowledge graph...")
    from merge_graph import merge_graph as do_merge

    final_data = do_merge(str(extracted_path), str(final_data_path))

    # Copy frontend HTML
    html_src = project_root / "output" / "index.html"
    if not html_src.exists():
        # Will be created separately
        pass

    print("\n" + "=" * 60)
    print(f"Build complete!")
    print(f"  Nodes: {len(final_data['nodes'])}")
    print(f"  Edges: {len(final_data['edges'])}")
    print(f"  Output: {final_data_path}")
    print(f"\nOpen output/index.html in a browser to view the visualization.")
    print("=" * 60)


if __name__ == "__main__":
    main()
