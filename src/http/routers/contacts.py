from fastapi import APIRouter

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("")
async def list_contacts(user_id: str = "default"):
    """List all contacts."""
    from src.tools.contacts.tools import contacts_list

    result = contacts_list.invoke({"user_id": user_id})
    return {"contacts": result}


@router.get("/search")
async def search_contacts(query: str, user_id: str = "default"):
    """Search contacts."""
    from src.tools.contacts.tools import contacts_search

    result = contacts_search.invoke({"user_id": user_id, "query": query})
    return {"results": result}


@router.post("")
async def add_contact(
    email: str,
    name: str | None = None,
    phone: str | None = None,
    company: str | None = None,
    user_id: str = "default",
):
    """Add a new contact."""
    from src.tools.contacts.tools import contacts_add

    args = {"user_id": user_id, "email": email}
    if name is not None:
        args["name"] = name
    if phone is not None:
        args["phone"] = phone
    if company is not None:
        args["company"] = company
    result = contacts_add.invoke(args)
    return {"result": str(result)}


@router.put("/{contact_id}")
async def update_contact(
    contact_id: str,
    email: str | None = None,
    name: str | None = None,
    phone: str | None = None,
    company: str | None = None,
    user_id: str = "default",
):
    """Update a contact."""
    from src.tools.contacts.tools import contacts_update

    args = {"user_id": user_id, "contact_id": contact_id}
    if email is not None:
        args["email"] = email
    if name is not None:
        args["name"] = name
    if phone is not None:
        args["phone"] = phone
    if company is not None:
        args["company"] = company
    result = contacts_update.invoke(args)
    return {"result": str(result)}


@router.delete("/{contact_id}")
async def delete_contact(contact_id: str, user_id: str = "default"):
    """Delete a contact."""
    from src.tools.contacts.tools import contacts_delete

    result = contacts_delete.invoke({"user_id": user_id, "contact_id": contact_id})
    return {"result": str(result)}
