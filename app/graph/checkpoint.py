from typing import Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from app.core.logging import logger

_in_memory_checkpointer = MemorySaver()


async def get_checkpointer(dsn: Optional[str] = None) -> BaseCheckpointSaver:
    """
    Returns a PostgreSQL-backed checkpointer when configured and reachable,
    otherwise returns a safe in-memory checkpointer for thread state restoration.
    """
    if dsn and "postgresql" in dsn:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            # Initialize async postgres saver
            saver = AsyncPostgresSaver.from_conn_string(dsn)
            # Create internal checkpoint tables if not already present
            await saver.setup()
            return saver
        except Exception as e:
            logger.warning(f"Could not initialize AsyncPostgresSaver ({e}), falling back to MemorySaver.")
    
    return _in_memory_checkpointer
