import math
from agentkit.rag.embeddings import hash_embed

def _cos(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))

def test_hash_embed_deterministic_and_semantically_ordered():
    a = hash_embed('double entry debits equal credits before posting')
    b = hash_embed('debits equal credits in double entry posting')
    c = hash_embed('weather forecast rain tomorrow morning clouds')
    assert a == hash_embed('double entry debits equal credits before posting')
    assert _cos(a, b) > _cos(a, c)