def chunk_text(s: str, max_chars: int = 8000, overlap: int = 400) -> list[str]:
    """Naive char-based chunking to respect prompt limits."""
    if not s: return []
    if len(s) <= max_chars: return [s]
    chunks = []
    start = 0
    while start < len(s):
        end = min(len(s), start + max_chars)
        chunks.append(s[start:end])
        if end == len(s): break
        start = max(0, end - overlap)
    return chunks

def merge_payloads(payloads: list[dict]) -> dict:
    out = {"flashcards": [], "mcqs": [], "mock_exam": {"title":"Merged Mock Exam","questions":[]}}
    for p in payloads:
        out["flashcards"].extend(p.get("flashcards", []))
        out["mcqs"].extend(p.get("mcqs", []))
        me = p.get("mock_exam", {})
        out["mock_exam"]["questions"].extend(me.get("questions", []))
    # light dedupe by question text
    seen = set()
    fc = []
    for x in out["flashcards"]:
        k = (x.get("q","").strip(), x.get("a","").strip())
        if k not in seen:
            seen.add(k); fc.append(x)
    out["flashcards"] = fc[:25]
    seen = set(); mcq=[]
    for x in out["mcqs"]:
        k = x.get("q","").strip()
        if k not in seen:
            seen.add(k); mcq.append(x)
    out["mcqs"] = mcq[:20]
    out["mock_exam"]["questions"] = out["mock_exam"]["questions"][:10]
    return out
