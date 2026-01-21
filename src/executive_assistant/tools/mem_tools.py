"""Memory tools for storing and retrieving user memories and preferences."""

from langchain_core.tools import tool

from executive_assistant.storage.mem_storage import get_mem_storage



@tool
def create_memory(
    content: str,
    memory_type: str = "note",
    key: str | None = None,
    confidence: float = 1.0,
) -> str:
    """
    Create or update a memory entry.

    Args:
        content: The memory content to store.
        memory_type: Type of memory. Options: profile, preference, fact, task, note.
        key: Optional normalized key for deduplication (e.g., "timezone", "language").
        confidence: Confidence score from 0.0 to 1.0. Default is 1.0.

    Returns:
        Confirmation message with memory ID.

    Examples:
        >>> create_memory("User prefers Python over JavaScript", "preference", "language")
        "Memory updated: [ID]"
        >>> create_memory("User lives in New York", "fact", "location")
        "Memory updated: [ID]"
    """
    storage = get_mem_storage()

    if key:
        existing = storage.get_memory_by_key(key)
        if existing:
            existing_content = (existing.get("content") or "").strip()
            if existing_content == content.strip():
                return f"Memory already exists: {existing['id']}"
            storage.update_memory(
                memory_id=existing["id"],
                content=content,
                confidence=confidence,
            )
            return f"Memory updated: {existing['id']}"

    existing = storage.get_memory_by_content(content)
    if existing:
        return f"Memory already exists: {existing['id']}"

    memory_id = storage.create_memory(
        content=content,
        memory_type=memory_type,
        key=key,
        confidence=confidence,
    )
    return f"Memory saved with ID: {memory_id}"

@tool
def update_memory(
    memory_id: str,
    content: str | None = None,
    confidence: float | None = None,
    status: str | None = None,
) -> str:
    """
    Update an existing memory.

    Args:
        memory_id: UUID of the memory to update.
        content: New content (optional).
        confidence: New confidence score from 0.0 to 1.0 (optional).
        status: New status: active, deprecated, or deleted (optional).

    Returns:
        Confirmation message or "not found" error.

    Examples:
        >>> update_memory("abc-123", content="Updated content")
        "Memory updated: abc-123"
        >>> update_memory("abc-123", status="deleted")
        "Memory marked as deleted: abc-123"
    """
    storage = get_mem_storage()
    success = storage.update_memory(
        memory_id=memory_id,
        content=content,
        confidence=confidence,
        status=status,
    )
    if success:
        return f"Memory updated: {memory_id}"
    return f"Memory not found: {memory_id}"


@tool
def delete_memory(memory_id: str) -> str:
    """
    Delete (soft delete) a memory by marking it as deleted.

    Args:
        memory_id: UUID of the memory to delete.

    Returns:
        Confirmation message or "not found" error.

    Examples:
        >>> delete_memory("abc-123")
        "Memory deleted: abc-123"
    """
    storage = get_mem_storage()
    success = storage.delete_memory(memory_id)
    if success:
        return f"Memory deleted: {memory_id}"
    return f"Memory not found: {memory_id}"


@tool
def forget_memory(memory_id: str) -> str:
    """
    Forget a memory (alias to delete_memory).

    Use this when users ask to "forget" something.

    Args:
        memory_id: UUID of the memory to forget.

    Returns:
        Confirmation message or "not found" error.

    Examples:
        >>> forget_memory("abc-123")
        "Memory forgotten: abc-123"
    """
    return delete_memory(memory_id)


@tool
def list_memories(
    memory_type: str | None = None,
    status: str = "active",
) -> str:
    """
    List all memories for the current thread.

    Args:
        memory_type: Filter by memory type: profile, preference, fact, task, note.
        status: Filter by status: active, deprecated, deleted. Default is "active".

    Returns:
        List of memories with their details.

    Examples:
        >>> list_memories()
        "ID: abc-123 | Type: preference | Content: User prefers Python..."
        >>> list_memories(memory_type="preference")
        "ID: abc-123 | Type: preference | Content: User prefers Python..."
    """
    storage = get_mem_storage()
    memories = storage.list_memories(memory_type=memory_type, status=status)

    if not memories:
        return "No memories found."

    lines = []
    for m in memories:
        lines.append(
            f"ID: {m['id'][:8]}... | Type: {m['memory_type']} | "
            f"Key: {m['key'] or 'N/A'} | Confidence: {m['confidence']:.2f}\n"
            f"Content: {m['content'][:100]}{'...' if len(m['content']) > 100 else ''}"
        )

    return "\n\n".join(lines)


@tool
def search_memories(
    query: str,
    limit: int = 5,
    min_confidence: float = 0.0,
) -> str:
    """
    Search memories by content using full-text search.

    Args:
        query: Search query string.
        limit: Maximum number of results to return. Default is 5.
        min_confidence: Minimum confidence score (0.0 to 1.0). Default is 0.0.

    Returns:
        List of matching memories with their details.

    Examples:
        >>> search_memories("python")
        "ID: abc-123 | Type: preference | Content: User prefers Python..."
        >>> search_memories("location", limit=3)
        "ID: def-456 | Type: fact | Content: User lives in New York..."
    """
    storage = get_mem_storage()
    memories = storage.search_memories(
        query=query,
        limit=limit,
        min_confidence=min_confidence,
    )

    if not memories:
        return f"No memories found matching: {query}"

    lines = []
    for m in memories:
        lines.append(
            f"ID: {m['id'][:8]}... | Type: {m['memory_type']} | "
            f"Key: {m['key'] or 'N/A'} | Confidence: {m['confidence']:.2f}\n"
            f"Content: {m['content'][:100]}{'...' if len(m['content']) > 100 else ''}"
        )

    return "\n\n".join(lines)


@tool
def get_memory_by_key(key: str) -> str:
    """
    Get a memory by its key (most recent active).

    Use this for retrieving specific memories like "timezone", "language", etc.

    Args:
        key: The memory key to look up.

    Returns:
        Memory content or "not found" error.

    Examples:
        >>> get_memory_by_key("timezone")
        "User's timezone: America/New_York"
        >>> get_memory_by_key("language")
        "User prefers English"
    """
    storage = get_mem_storage()
    memory = storage.get_memory_by_key(key)

    if memory:
        return f"Key: {memory['key']} | Type: {memory['memory_type']} | Content: {memory['content']}"

    return f"No memory found with key: {key}"


@tool
def normalize_or_create_memory(
    key: str,
    content: str,
    memory_type: str = "preference",
    confidence: float = 1.0,
) -> str:
    """
    Normalize a memory by key: deprecate old version, create new one.

    Use this when updating existing keyed memories like preferences.

    Args:
        key: The memory key (e.g., "timezone", "language").
        content: New content for the memory.
        memory_type: Type of memory. Default is "preference".
        confidence: Confidence score from 0.0 to 1.0. Default is 1.0.

    Returns:
        Confirmation message with memory ID and whether it was new.

    Examples:
        >>> normalize_or_create_memory("timezone", "America/New_York")
        "Memory updated: abc-123 (was existing)"
        >>> normalize_or_create_memory("color", "blue")
        "Memory created: def-456 (new)"
    """
    storage = get_mem_storage()
    memory_id, is_new = storage.normalize_or_create(
        key=key,
        content=content,
        memory_type=memory_type,
        confidence=confidence,
    )

    action = "created" if is_new else "updated"
    return f"Memory {action}: {memory_id}"


def get_memory_tools() -> list:
    """
    Get all memory tools for the agent.

    Returns:
        List of memory-related LangChain tools.
    """
    return [
        create_memory,
        update_memory,
        delete_memory,
        forget_memory,
        list_memories,
        search_memories,
        get_memory_by_key,
        normalize_or_create_memory,
    ]
