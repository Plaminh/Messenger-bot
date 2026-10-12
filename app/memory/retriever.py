"""Memory retrieval and composite re-ranking.

Finds relevant memories using vector similarity, then re-ranks via:
score = A*cosine + B*exp(-Δdays/TAU) + C*(importance/10)
Updates last_accessed_at for top memories.
"""

from datetime import datetime, timezone
import math
from typing import List, Tuple
import numpy as np
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.db.models import Memory

logger = get_logger(__name__)


def compute_python_cosine(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two float vectors using numpy."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


async def retrieve_relevant_memories(
    session: AsyncSession,
    user_id: int,
    query_vector: list[float],
    *,
    candidate_limit: int = 20,
    top_k: int = 6,
) -> list[Memory]:
    """Retrieve top-k relevant memories for a user using composite reranking."""
    settings = get_settings()
    weight_a = settings.RETRIEVER_WEIGHT_COSINE
    weight_b = settings.RETRIEVER_WEIGHT_RECENCY
    weight_c = settings.RETRIEVER_WEIGHT_IMPORTANCE
    tau_days = settings.RETRIEVER_TAU_DAYS

    candidates: list[tuple[Memory, float]] = []

    # Check dialect for pgvector support vs Python fallback (e.g. SQLite tests)
    bind = session.get_bind()
    is_postgres = bind and "postgresql" in bind.dialect.name

    if is_postgres:
        try:
            # PostgreSQL with pgvector cosine distance operator <=>
            distance_col = Memory.embedding.cosine_distance(query_vector).label("distance")
            stmt = (
                select(Memory, distance_col)
                .where(Memory.user_id == user_id)
                .order_by(distance_col.asc())
                .limit(candidate_limit)
            )
            result = await session.execute(stmt)
            for mem, dist in result.all():
                cosine_sim = 1.0 - float(dist)
                candidates.append((mem, cosine_sim))
        except Exception as exc:
            logger.warning("pgvector cosine query failed, falling back to python ranking: %s", exc)
            candidates = []

    if not candidates:
        # Fallback for SQLite or when pgvector query is not applicable
        stmt = (
            select(Memory)
            .where(Memory.user_id == user_id)
            .limit(candidate_limit * 2)
        )
        result = await session.execute(stmt)
        memories = list(result.scalars().all())
        for mem in memories:
            cos = compute_python_cosine(query_vector, mem.embedding)
            candidates.append((mem, cos))

    if not candidates:
        return []

    # Composite reranking: A*cosine + B*exp(-Δdays/TAU) + C*(importance/10)
    now = datetime.now(timezone.utc)
    scored_candidates: list[tuple[float, Memory]] = []

    for mem, cosine in candidates:
        # Calculate days elapsed since last access (or created)
        last_accessed = mem.last_accessed_at
        if last_accessed is None:
            last_accessed = mem.created_at

        if last_accessed.tzinfo is None:
            last_accessed = last_accessed.replace(tzinfo=timezone.utc)

        delta_days = max(0.0, (now - last_accessed).total_seconds() / 86400.0)
        recency = math.exp(-delta_days / tau_days)
        importance_norm = mem.importance / 10.0

        composite_score = (weight_a * cosine) + (weight_b * recency) + (weight_c * importance_norm)
        scored_candidates.append((composite_score, mem))

    # Sort descending by composite score
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    top_memories = [mem for _, mem in scored_candidates[:top_k]]

    # Update last_accessed_at for used memories
    if top_memories:
        top_ids = [m.id for m in top_memories]
        update_stmt = (
            update(Memory)
            .where(Memory.id.in_(top_ids))
            .values(last_accessed_at=func.now())
        )
        await session.execute(update_stmt)
        await session.commit()

    return top_memories
