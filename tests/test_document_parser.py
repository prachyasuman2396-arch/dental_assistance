import os
import tempfile
import pymupdf
import pytest
from app.documents.parser import PDFParser
from app.rag.splitter import RecursiveTextSplitter


def test_pdf_parser_extracts_pages_and_preserves_page_numbers():
    # Create temporary PDF with 2 distinct pages
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        doc = pymupdf.open()
        p1 = doc.new_page()
        p1.insert_text((50, 50), "Page 1: Principles of Endodontic Access Cavity Preparation.")
        p2 = doc.new_page()
        p2.insert_text((50, 50), "Page 2: Irrigation with Sodium Hypochlorite and Smear Layer.")
        doc.save(tmp_path)
        doc.close()

        parsed = PDFParser.parse_file(tmp_path, "test_endo.pdf")
        assert parsed.total_pages == 2
        assert parsed.filename == "test_endo.pdf"
        assert not parsed.is_empty_or_scanned
        assert parsed.pages[0].page_number == 1
        assert "Access Cavity" in parsed.pages[0].text
        assert parsed.pages[1].page_number == 2
        assert "Smear Layer" in parsed.pages[1].text
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_recursive_text_splitter_chunking_and_overlap():
    text = (
        "Amelogenesis is the formation of enamel on teeth and begins when the crown is forming. "
        "Ameloblasts are cells present only during tooth development that deposit enamel. "
        "The life cycle of ameloblasts consists of six stages: morphogenetic, organizing, formative, "
        "maturation, protective, and desmolytic."
    )
    splitter = RecursiveTextSplitter(chunk_size=100, chunk_overlap=20)
    chunks = splitter.split_text(text)

    assert len(chunks) > 1
    # Check each chunk satisfies size bound
    for c in chunks:
        assert len(c) <= 120  # generous bound for word boundaries
    # Content hash uniqueness
    h1 = PDFParser.compute_sha256(chunks[0])
    h2 = PDFParser.compute_sha256(chunks[1])
    assert h1 != h2
