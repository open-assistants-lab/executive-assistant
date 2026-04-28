from fastapi import APIRouter

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("")
async def list_todos(user_id: str = "default_user"):
    """List all todos."""
    from src.sdk.tools_core.todos import todos_list

    result = todos_list.invoke({"user_id": user_id})
    return {"todos": result}


@router.post("")
async def add_todo(
    content: str,
    priority: int | None = None,
    user_id: str = "default_user",
):
    """Add a new todo."""
    from src.sdk.tools_core.todos import todos_add

    args = {"user_id": user_id, "content": content}
    if priority is not None:
        args["priority"] = str(priority)
    result = todos_add.invoke(args)
    return {"result": str(result)}


@router.put("/{todo_id}")
async def update_todo(
    todo_id: str,
    content: str | None = None,
    status: str | None = None,
    priority: int | None = None,
    user_id: str = "default_user",
):
    """Update a todo."""
    from src.sdk.tools_core.todos import todos_update

    args = {"user_id": user_id, "todo_id": todo_id}
    if content is not None:
        args["content"] = content
    if status is not None:
        args["status"] = status
    if priority is not None:
        args["priority"] = priority
    result = todos_update.invoke(args)
    return {"result": str(result)}


@router.delete("/{todo_id}")
async def delete_todo(todo_id: str, user_id: str = "default_user"):
    """Delete a todo."""
    from src.sdk.tools_core.todos import todos_delete

    result = todos_delete.invoke({"user_id": user_id, "todo_id": todo_id})
    return {"result": str(result)}
