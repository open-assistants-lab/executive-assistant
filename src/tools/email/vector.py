"""Email semantic search using ChromaDB."""

from pathlib import Path

import chromadb
import chromadb.config


class EmailVectorStore:
    """ChromaDB-based email semantic search.

    Stores email content embeddings for semantic search.
    """

    def __init__(self, user_id: str):
        if not user_id or user_id == "default":
            raise ValueError(f"Invalid user_id: {user_id}")
        self.user_id = user_id
        base_path = Path(f"data/users/{user_id}/email")
        base_path.mkdir(parents=True, exist_ok=True)

        self.vector_path = str((base_path / "vectors").resolve())

        self.chroma = chromadb.PersistentClient(
            path=self.vector_path,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )

        self.collection = self.chroma.get_or_create_collection(
            name="emails",
            metadata={"user_id": user_id},
        )

    def add_email(
        self,
        email_id: str,
        subject: str,
        from_addr: str,
        to_addrs: str,
        cc_addrs: str | None,
        body_text: str,
        metadata: dict | None = None,
    ) -> None:
        """Add email to vector store."""
        # Include subject/from/to/cc in searchable document
        search_doc = f"{subject}\n{from_addr}\n{to_addrs}"
        if cc_addrs:
            search_doc += f"\n{cc_addrs}"
        search_doc += f"\n{body_text}"

        # Store as metadata for filtering
        meta = {
            "subject": subject,
            "from": from_addr,
            "to": to_addrs,
            **(metadata or {}),
        }
        if cc_addrs:
            meta["cc"] = cc_addrs

        self.collection.upsert(
            ids=[email_id],
            documents=[search_doc],
            metadatas=[meta],
        )

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search emails by semantic similarity."""
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
        )

        emails = []
        if results["ids"] and results["ids"][0]:
            for i, email_id in enumerate(results["ids"][0]):
                emails.append(
                    {
                        "id": email_id,
                        "score": 1 - (results["distances"][0][i] if results["distances"] else 0),
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    }
                )

        return emails

    def delete_email(self, email_id: str) -> None:
        """Delete email from vector store."""
        self.collection.delete(ids=[email_id])

    def clear(self) -> None:
        """Clear all emails from vector store."""
        self.collection.delete(where={"user_id": self.user_id})


def get_email_vector_store(user_id: str) -> EmailVectorStore:
    """Get email vector store for user."""
    return EmailVectorStore(user_id)
