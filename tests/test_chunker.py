from api.rag.chunker import chunk_markdown

DOC = """# Manual

Short intro of the leave manual for every employee of the company.

## Requests

To request leave you open Time Off and create a new request for the dates you need.

### Approval

Your direct manager approves the request within three working days.

## Empty

## Balance

The balance is computed as allocated minus taken.
"""


def test_heading_path_is_kept():
    chunks = chunk_markdown(DOC, "m.md")
    headings = [c.heading for c in chunks]
    assert "Manual > Requests > Approval" in headings
    assert "Manual > Balance" in headings  # the previous level-3 heading does not leak into its sibling


def test_empty_sections_are_skipped():
    assert all("Empty" not in c.heading for c in chunk_markdown(DOC, "m.md"))


def test_heading_is_prepended_for_embedding():
    c = next(c for c in chunk_markdown(DOC, "m.md") if c.heading.endswith("Approval"))
    assert c.text_for_embedding.startswith("Manual > Requests > Approval")


def test_long_section_is_split_with_overlap_and_size_limit():
    body = "\n\n".join(f"Paragraph {i}. " + "word " * 40 for i in range(20))
    chunks = chunk_markdown(f"# T\n\n{body}", "l.md", max_chars=500, overlap=80)
    assert len(chunks) > 3
    assert all(len(c.content) <= 500 + 80 + 2 for c in chunks)
    assert chunks[0].content[-30:] in chunks[1].content  # overlap between consecutive chunks


def test_single_giant_paragraph_is_windowed():
    chunks = chunk_markdown("# T\n\n" + "x" * 3000, "g.md", max_chars=1000, overlap=100)
    assert len(chunks) >= 3 and all(len(c.content) <= 1000 for c in chunks)


def test_hash_inside_code_block_is_not_a_heading():
    doc = "# A\n\nenough text to pass the minimum length\n\n```\n# shell comment\nls\n```\n"
    assert [c.heading for c in chunk_markdown(doc, "c.md")] == ["A"]


def test_same_content_same_hash():
    from api.rag.store import content_hash
    a, b = chunk_markdown(DOC, "m.md"), chunk_markdown(DOC, "m.md")
    assert [content_hash(c) for c in a] == [content_hash(c) for c in b]


def test_changing_the_text_changes_the_hash():
    from api.rag.store import content_hash
    a = chunk_markdown(DOC, "m.md")[0]
    b = chunk_markdown(DOC.replace("three working days", "five working days"), "m.md")
    assert content_hash(a) in {content_hash(c) for c in b}  # untouched chunk keeps its hash
    changed = next(c for c in b if "five working days" in c.content)
    assert content_hash(changed) not in {content_hash(c) for c in chunk_markdown(DOC, "m.md")}
