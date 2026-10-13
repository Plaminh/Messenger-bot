"""Bounded deterministic retrieval for durable text memories.

Candidates are filtered by user and keyword matches in SQL, then ranked with
keyword overlap (0.55), recency (0.25), and importance (0.20). This is a
small heuristic rather than semantic search. Greetings with no useful terms
fall back to recent and important memories.
"""

from datetime import datetime, timezone
import math
import re
import unicodedata

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Memory

MAX_MEMORY_CHARS = 3000
VIETNAMESE_STOPWORDS = {"và", "là", "cho", "mình", "bạn", "của", "có", "nhé", "nha", "ơi", "rồi"}
_VIETNAMESE_SOURCE = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
_VIETNAMESE_ASCII = "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"


def normalize_memory_text(text: str) -> str:
    """Normalize case, accents, whitespace, and punctuation consistently."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    without_marks = without_marks.replace("đ", "d")
    return re.sub(r"[^\w]+", " ", without_marks, flags=re.UNICODE).strip()


def extract_keywords(text: str) -> list[str]:
    """Extract useful normalized terms, treating accented and plain text alike."""
    stopwords = {normalize_memory_text(word) for word in VIETNAMESE_STOPWORDS}
    return [word for word in normalize_memory_text(text).split() if len(word) >= 2 and word not in stopwords]


async def retrieve_relevant_memories(
    session: AsyncSession,
    user_id: int,
    query_text: str,
    *,
    candidate_limit: int = 30,
    top_k: int = 6,
) -> list[Memory]:
    """Return bounded, user-isolated memories ranked without loading the table."""
    candidate_limit = max(1, min(candidate_limit, 50))
    top_k = max(1, min(top_k, 10))
    keywords = extract_keywords(query_text)

    ordering = (Memory.last_accessed_at.desc(), Memory.importance.desc(), Memory.id.desc())
    stmt = select(Memory).where(Memory.user_id == user_id)
    bind = session.get_bind()
    if keywords and bind is not None and bind.dialect.name == "postgresql":
        # PostgreSQL does the user filter and keyword candidate selection. translate
        # gives deterministic accented/unaccented matching without an extension.
        searchable = func.translate(func.lower(Memory.content), _VIETNAMESE_SOURCE, _VIETNAMESE_ASCII)
        stmt = stmt.where(or_(*(searchable.contains(term) for term in set(keywords))))
    stmt = stmt.order_by(*ordering).limit(candidate_limit)
    result = await session.execute(stmt)
    candidates = list(result.scalars().all())
    if not candidates:
        return []

    query_terms = set(keywords)
    now = datetime.now(timezone.utc)
    scored: list[tuple[float, Memory]] = []
    for memory in candidates:
        last_accessed = memory.last_accessed_at or memory.created_at
        if last_accessed.tzinfo is None:
            last_accessed = last_accessed.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - last_accessed).total_seconds() / 86400.0)
        recency = math.exp(-age_days / 14.0)
        memory_terms = set(extract_keywords(memory.content))
        keyword_score = len(memory_terms & query_terms) / len(query_terms) if query_terms else 0.0
        if query_terms and keyword_score == 0:
            continue
        score = (0.55 * keyword_score) + (0.25 * recency) + (0.20 * (memory.importance / 10.0))
        scored.append((score, memory))

    # No useful terms (for example a greeting): return a small deterministic
    # recent/important fallback. With useful terms, unrelated rows are excluded.
    if not query_terms:
        scored = [
            (
                0.25 * math.exp(-max(0.0, (now - ((m.last_accessed_at or m.created_at).replace(tzinfo=timezone.utc) if (m.last_accessed_at or m.created_at).tzinfo is None else (m.last_accessed_at or m.created_at))).total_seconds() / 86400.0) / 14.0)
                + 0.20 * (m.importance / 10.0),
                m,
            )
            for m in candidates
        ]
        top_k = min(top_k, 3)
    scored.sort(key=lambda item: (item[0], item[1].id), reverse=True)
    selected: list[Memory] = []
    total_chars = 0
    for _, memory in scored:
        if len(selected) >= top_k or total_chars + len(memory.content) > MAX_MEMORY_CHARS:
            continue
        selected.append(memory)
        total_chars += len(memory.content)

    return selected
