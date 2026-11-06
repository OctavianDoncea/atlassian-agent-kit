from agentkit.rag.chunking import chunk_document

def test_chunk_sizes_and_overlap():
    text = ('alpha beta gamma delta ' * 60) + '\n\n' + ('epsilon zeta eta theta ' * 60)
    chunks = chunk_document('doc.md', text, size=200, overlap=50)
    assert len(chunks) >= 2
    assert all(len(c.content) <= 260 for c in chunks)
    assert chunks[1].content.startswith(chunks[0].content[-50:])


def test_content_hash_is_deterministic():
    a = chunk_document('a.md', 'same content here', size=100, overlap=0)
    b = chunk_document('b.md', 'same content here', size=100, overlap=0)
    assert a[0].content_hash == b[0].content_hash
    assert a[0].chunk_index == 0 and a[0].source == 'a.md'