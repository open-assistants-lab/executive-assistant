"""
Identity merge tools for user identity consolidation.

These tools allow users to:
1. Request identity merge (initiate verification)
2. Confirm identity merge (complete verification)
3. Merge additional identities (add more threads to existing user)
"""

import random
import string
from datetime import datetime, timedelta, timezone
from typing import Literal

from langchain_core.tools import tool

from executive_assistant.storage.file_sandbox import get_thread_id
from executive_assistant.storage.user_registry import UserRegistry
from executive_assistant.storage.helpers import (
    generate_persistent_user_id,
    merge_user_data,
    sanitize_thread_id_to_user_id,
)


def _generate_verification_code(length: int = 6) -> str:
    """Generate a random numeric verification code."""
    return "".join(random.choices(string.digits, k=length))


def _get_code_expiration(minutes: int = 15) -> datetime:
    """Get expiration timestamp for verification code."""
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


@tool
def request_identity_merge(
    verification_contact: str,
    method: Literal["email", "phone"] = "email"
) -> str:
    """
    Request to merge current anonymous identity into a persistent user account.

    This initiates the verification process. A verification code will be generated
    and you should receive it via your chosen method (email/phone).

    After receiving the code, use confirm_identity_merge() to complete the merge.

    Args:
        verification_contact: Email address or phone number for verification
        method: Verification method - 'email' or 'phone'

    Returns:
        Confirmation message with verification code info

    Examples:
        >>> request_identity_merge(verification_contact="user@example.com")
        "Verification code sent to user@example.com. Check your email and use confirm_identity_merge(code='...') to complete."

        >>> request_identity_merge(verification_contact="+1234567890", method="phone")
        "Verification code sent to +1234567890. Use confirm_identity_merge(code='...') to complete."
    """
    try:
        thread_id = get_thread_id()
        if not thread_id:
            return "❌ Error: No thread context found. Are you in a conversation?"

        # Get identity from database
        registry = UserRegistry()
        import asyncio

        identity = asyncio.run(registry.get_identity_by_thread_id(thread_id))
        if not identity:
            return "❌ Error: No identity found for current thread."

        if identity.get("verification_status") == "verified":
            persistent_id = identity.get("persistent_user_id")
            return f"✅ Already verified! Your persistent user ID: {persistent_id}"

        # Generate verification code
        code = _generate_verification_code()
        expires_at = _get_code_expiration()

        # Store verification code and update status
        asyncio.run(registry.update_identity_pending(
            thread_id=thread_id,
            verification_method=method,
            verification_contact=verification_contact
        ))

        # Store code separately (need direct DB access)
        import asyncpg
        from executive_assistant.config import settings

        async def _store_code():
            conn = await asyncpg.connect(settings.POSTGRES_URL)
            try:
                await conn.execute("""
                    UPDATE identities
                    SET verification_code = $1,
                        code_expires_at = $2
                    WHERE thread_id = $3
                """, code, expires_at, thread_id)
            finally:
                await conn.close()

        asyncio.run(_store_code())

        # TODO: Actually send the code via email/SMS
        # For now, just return it (in production, use SendGrid/Twilio)
        # _send_verification_code(verification_contact, method, code)

        return (
            f"✅ Verification initiated!\n\n"
            f"Contact: {verification_contact}\n"
            f"Method: {method}\n\n"
            f"📋 Your verification code: **{code}**\n\n"
            f"Use confirm_identity_merge(code='{code}') to complete the merge.\n"
            f"⏰ Code expires in 15 minutes."
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error initiating merge: {e}"


@tool
def confirm_identity_merge(code: str) -> str:
    """
    Complete identity merge after verifying the code.

    This will:
    1. Verify the code is correct and not expired
    2. Generate a persistent user_id (user_*)
    3. Move all your data from anon_* to user_* directory
    4. Update your identity record

    Args:
        code: Verification code received via email/phone

    Returns:
        Success message with new persistent user_id

    Examples:
        >>> confirm_identity_merge(code="123456")
        "✅ Identity merged! Your persistent user ID: user_abc123..."
    """
    try:
        thread_id = get_thread_id()
        if not thread_id:
            return "❌ Error: No thread context found."

        registry = UserRegistry()
        import asyncio

        # Get current identity
        identity = asyncio.run(registry.get_identity_by_thread_id(thread_id))
        if not identity:
            return "❌ Error: No identity found for current thread."

        # Check if already verified
        if identity.get("verification_status") == "verified":
            persistent_id = identity.get("persistent_user_id")
            return f"✅ Already verified! Your persistent user ID: {persistent_id}"

        # Verify code
        import asyncpg
        from executive_assistant.config import settings

        async def _verify_code():
            conn = await asyncpg.connect(settings.POSTGRES_URL)
            try:
                result = await conn.fetchrow("""
                    SELECT verification_code, code_expires_at, verification_contact
                    FROM identities
                    WHERE thread_id = $1
                """, thread_id)
                return result
            finally:
                await conn.close()

        result = asyncio.run(_verify_code())
        if not result:
            return "❌ Error: Identity not found."

        stored_code = result.get("verification_code")
        expires_at = result.get("code_expires_at")

        # Validate code
        if not stored_code:
            return "❌ No verification code found. Use request_identity_merge() first."

        if stored_code != code:
            return f"❌ Invalid code. Please check and try again.\n\n(Entered: {code}, Expected: {stored_code})"

        if expires_at and datetime.now(timezone.utc) > expires_at:
            return "❌ Code has expired. Please request a new one with request_identity_merge()."

        # Generate persistent user_id
        persistent_user_id = generate_persistent_user_id()

        # Get old user_id (anon_*) for data migration
        old_user_id = sanitize_thread_id_to_user_id(thread_id)

        # Merge data (move from anon_* to user_*)
        merge_result = merge_user_data(
            source_user_id=old_user_id,
            target_user_id=persistent_user_id,
            source_thread_id=thread_id
        )

        # Update identity record
        asyncio.run(registry.update_identity_merge(
            identity_id=identity["identity_id"],
            persistent_user_id=persistent_user_id,
            verification_status="verified"
        ))

        # Clear verification code
        async def _clear_code():
            conn = await asyncpg.connect(settings.POSTGRES_URL)
            try:
                await conn.execute("""
                    UPDATE identities
                    SET verification_code = NULL,
                        code_expires_at = NULL
                    WHERE thread_id = $1
                """, thread_id)
            finally:
                await conn.close()

        asyncio.run(_clear_code())

        # Format response
        items_moved = []
        if merge_result.get("files_moved"):
            items_moved.append(f"{len(merge_result['files_moved'])} files")
        if merge_result.get("dbs_moved"):
            items_moved.append(f"{len(merge_result['dbs_moved'])} databases")
        if merge_result.get("vs_moved"):
            items_moved.append(f"{len(merge_result['vs_moved'])} VS collections")

        conflicts = merge_result.get("conflicts_renamed", [])
        conflict_msg = f"\n⚠️ {len(conflicts)} conflicts renamed" if conflicts else ""

        return (
            f"✅ **Identity merged successfully!**\n\n"
            f"Your persistent user ID: `{persistent_user_id}`\n\n"
            f"Data moved: {', '.join(items_moved) if items_moved else 'None'}{conflict_msg}\n\n"
            f"You can now use merge_additional_identity() to add other threads to this account."
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error completing merge: {e}"


@tool
def merge_additional_identity(thread_id_to_merge: str) -> str:
    """
    Merge another anonymous identity into your current persistent user account.

    Use this after you've already verified your own identity to consolidate
    multiple threads (e.g., Telegram + Email + HTTP) into one account.

    Args:
        thread_id_to_merge: Thread ID to merge (e.g., "telegram:123456" or "email:user@example.com")

    Returns:
        Success message

    Examples:
        >>> merge_additional_identity(thread_id_to_merge="email:user@example.com")
        "✅ Merged email:user@example.com into your account"

        >>> merge_additional_identity(thread_id_to_merge="http:session_abc123")
        "✅ Merged http:session_abc123 into your account"
    """
    try:
        current_thread_id = get_thread_id()
        if not current_thread_id:
            return "❌ Error: No thread context found."

        # Validate thread_id_to_merge format
        if ":" not in thread_id_to_merge:
            return (
                "❌ Invalid thread_id format. Expected format: 'channel:id'\n"
                "Examples: 'telegram:123456', 'email:user@example.com', 'http:session_abc'"
            )

        registry = UserRegistry()
        import asyncio

        # Get current identity
        current_identity = asyncio.run(registry.get_identity_by_thread_id(current_thread_id))
        if not current_identity:
            return "❌ Error: No identity found for current thread."

        # Check if current user is verified
        if current_identity.get("verification_status") != "verified":
            return "❌ You must verify your own identity first. Use request_identity_merge() and confirm_identity_merge()."

        persistent_user_id = current_identity.get("persistent_user_id")
        if not persistent_user_id:
            return "❌ Error: You don't have a persistent user ID. Please verify first."

        # Get identity to merge
        target_identity = asyncio.run(registry.get_identity_by_thread_id(thread_id_to_merge))
        if not target_identity:
            return f"❌ Error: Identity not found for thread '{thread_id_to_merge}'."

        # Check if target is already verified and merged to same user
        target_persistent = target_identity.get("persistent_user_id")
        if target_persistent == persistent_user_id:
            return f"✅ Already merged! '{thread_id_to_merge}' is already part of your account."

        # Check if target is already verified to a different user
        if target_persistent:
            return f"⚠️ '{thread_id_to_merge}' is already merged to a different user: {target_persistent}"

        # Get old user_id for data migration
        old_user_id = target_identity.get("identity_id")
        if not old_user_id:
            old_user_id = sanitize_thread_id_to_user_id(thread_id_to_merge)

        # Merge data (move from anon_* to user_*)
        merge_result = merge_user_data(
            source_user_id=old_user_id,
            target_user_id=persistent_user_id,
            source_thread_id=thread_id_to_merge
        )

        # Update target identity
        asyncio.run(registry.update_identity_merge(
            identity_id=target_identity["identity_id"],
            persistent_user_id=persistent_user_id,
            verification_status="verified"
        ))

        # Format response
        items_moved = []
        if merge_result.get("files_moved"):
            items_moved.append(f"{len(merge_result['files_moved'])} files")
        if merge_result.get("dbs_moved"):
            items_moved.append(f"{len(merge_result['dbs_moved'])} databases")
        if merge_result.get("vs_moved"):
            items_moved.append(f"{len(merge_result['vs_moved'])} VS collections")

        conflicts = merge_result.get("conflicts_renamed", [])
        conflict_msg = f"\n⚠️ {len(conflicts)} conflicts renamed" if conflicts else ""

        return (
            f"✅ **Merged '{thread_id_to_merge}' into your account!**\n\n"
            f"Your persistent user ID: `{persistent_user_id}`\n\n"
            f"Data moved: {', '.join(items_moved) if items_moved else 'None'}{conflict_msg}\n\n"
            f"All threads now share the same storage."
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error merging identity: {e}"


@tool
def get_my_identity() -> str:
    """
    Get information about your current identity.

    Shows your identity status, thread_id, and user_id information.

    Returns:
        Identity information string

    Examples:
        >>> get_my_identity()
        "Thread: telegram:123456
         Identity ID: anon_telegram_123456
         Status: anonymous
         Verified: No"
    """
    try:
        thread_id = get_thread_id()
        if not thread_id:
            return "❌ Error: No thread context found."

        registry = UserRegistry()
        import asyncio

        identity = asyncio.run(registry.get_identity_by_thread_id(thread_id))
        if not identity:
            return f"❌ No identity found for thread: {thread_id}"

        lines = [
            f"📋 **Your Identity Info**\n",
            f"Thread ID: `{identity.get('thread_id')}`",
            f"Identity ID: `{identity.get('identity_id')}`",
            f"Status: {identity.get('verification_status', 'unknown')}",
            f"Channel: {identity.get('channel', 'unknown')}",
        ]

        persistent_id = identity.get("persistent_user_id")
        if persistent_id:
            lines.append(f"Persistent User ID: `{persistent_id}` ✅")
            lines.append(f"Verified at: {identity.get('verified_at', 'N/A')}")
        else:
            lines.append("Persistent User ID: Not yet verified ❌")

        verification_method = identity.get("verification_method")
        if verification_method:
            lines.append(f"Verification Method: {verification_method}")
            lines.append(f"Contact: {identity.get('verification_contact', 'N/A')}")

        return "\n".join(lines)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error getting identity info: {e}"
