"""Instinct tools for behavioral pattern learning.

Instincts are atomic behavioral patterns (trigger → action) learned from user interactions.
They are automatically applied based on confidence scores and can evolve into skills.
"""

import json
from datetime import datetime, timezone

from langchain_core.tools import tool

from executive_assistant.storage.instinct_storage import get_instinct_storage


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


@tool
def create_instinct(
    trigger: str,
    action: str,
    domain: str,
    source: str = "session-observation",
    confidence: float = 0.5,
) -> str:
    """
    Create a new instinct (behavioral pattern).

    Instincts are learned automatically, but you can also create them manually
    when you detect clear patterns in user behavior.

    Args:
        trigger: When this instinct applies (e.g., "user asks quick questions")
        action: What to do (e.g., "respond briefly without detailed explanations")
        domain: Category: communication, format, workflow, tool_selection, verification, timing
        source: How learned: session-observation, explicit-user, repetition-confirmed
        confidence: Initial confidence (0.0 to 1.0, default 0.5)

    Returns:
        Confirmation message with instinct ID

    Examples:
        >>> create_instinct(
        ...     "user requests data export",
        ...     "return JSON format by default",
        ...     "format",
        ...     "explicit-user",
        ...     0.9
        ... )
        "Instinct created: [ID]"

        >>> create_instinct(
        ...     "user asks follow-up questions",
        ...     "be concise and direct",
        ...     "communication",
        ...     "session-observation",
        ...     0.6
        ... )
        "Instinct created: [ID]"
    """
    storage = get_instinct_storage()
    instinct_id = storage.create_instinct(
        trigger=trigger,
        action=action,
        domain=domain,
        source=source,
        confidence=confidence,
    )
    return f"Instinct created: {instinct_id}"


@tool
def list_instincts(
    domain: str | None = None,
    min_confidence: float = 0.0,
    limit: int = 10,
) -> str:
    """
    List all instincts for the current thread.

    Args:
        domain: Filter by domain (communication, format, workflow, etc.)
        min_confidence: Minimum confidence score (0.0 to 1.0)
        limit: Maximum number of results (default 10)

    Returns:
        Formatted list of instincts

    Examples:
        >>> list_instincts()
        "Instincts (3 total):\\n- concise-responses (0.8)\\n-..."

        >>> list_instincts(domain="communication")
        "Communication instincts (2 total):\\n-..."
    """
    storage = get_instinct_storage()
    instincts = storage.list_instincts(
        domain=domain,
        min_confidence=min_confidence,
    )

    if not instincts:
        return "No instincts found."

    lines = [f"Instincts ({len(instincts)} total):"]

    for instinct in instincts[:limit]:
        confidence = instinct["confidence"]
        trigger = instinct["trigger"][:50]
        action = instinct["action"][:50]

        lines.append(
            f"- {instinct['id'][:8]}... | {instinct['domain']} | Confidence: {confidence:.2f}\n"
            f"  Trigger: {trigger}...\n"
            f"  Action: {action}..."
        )

    return "\n".join(lines)


@tool
def adjust_instinct_confidence(
    instinct_id: str,
    delta: float,
) -> str:
    """
    Adjust instinct confidence up or down.

    Use this to reinforce or contradict learned patterns based on user feedback.

    Args:
        instinct_id: First 8+ characters of instinct ID
        delta: Adjustment amount (+0.05 to confirm, -0.1 to contradict)

    Returns:
        Confirmation message

    Examples:
        >>> adjust_instinct_confidence("abc123", 0.05)
        "Instinct abc123... confirmed: 0.75 → 0.80"

        >>> adjust_instinct_confidence("abc123", -0.1)
        "Instinct abc123... contradicted: 0.75 → 0.65"
    """
    storage = get_instinct_storage()

    # Find full ID by prefix
    instincts = storage.list_instincts()
    full_id = None
    for inst in instincts:
        if inst["id"].startswith(instinct_id):
            full_id = inst["id"]
            old_confidence = inst["confidence"]
            break

    if not full_id:
        return f"Instinct not found: {instinct_id}"

    success = storage.adjust_confidence(full_id, delta)

    if success:
        instinct = storage.get_instinct(full_id)
        new_confidence = instinct["confidence"]
        return f"Instinct {instinct_id[:8]}... adjusted: {old_confidence:.2f} → {new_confidence:.2f}"

    return f"Failed to adjust instinct: {instinct_id}"


@tool
def get_applicable_instincts(
    context: str,
    max_count: int = 5,
) -> str:
    """
    Get instincts applicable to current context.

    Use this to see which behavioral patterns should influence your response.

    Args:
        context: Current user message or situation
        max_count: Maximum number to return

    Returns:
        List of applicable instincts with their actions

    Examples:
        >>> get_applicable_instincts("Can you export the data?")
        "Applicable instincts (2):\\n- prefer-json: return JSON format...\\n-..."

        >>> get_applicable_instincts("Make it quick")
        "Applicable instincts (1):\\n- concise: be brief..."
    """
    storage = get_instinct_storage()
    instincts = storage.get_applicable_instincts(context, max_count=max_count)

    if not instincts:
        return "No applicable instincts found."

    lines = [f"Applicable instincts ({len(instincts)}):"]

    for instinct in instincts:
        lines.append(
            f"- {instinct['domain']}: {instinct['action']}\n"
            f"  (confidence: {instinct['confidence']:.2f}, trigger: {instinct['trigger'][:40]}...)"
        )

    return "\n".join(lines)


@tool
def disable_instinct(instinct_id: str) -> str:
    """
    Disable an instinct (stop applying it automatically).

    Args:
        instinct_id: First 8+ characters of instinct ID

    Returns:
        Confirmation message

    Examples:
        >>> disable_instinct("abc123")
        "Instinct abc123... disabled"
    """
    storage = get_instinct_storage()

    # Find full ID
    instincts = storage.list_instincts()
    full_id = None
    for inst in instincts:
        if inst["id"].startswith(instinct_id):
            full_id = inst["id"]
            break

    if not full_id:
        return f"Instinct not found: {instinct_id}"

    success = storage.set_instinct_status(full_id, "disabled")

    if success:
        return f"Instinct {instinct_id[:8]}... disabled"

    return f"Failed to disable instinct: {instinct_id}"


@tool
def enable_instinct(instinct_id: str) -> str:
    """
    Re-enable a disabled instinct.

    Args:
        instinct_id: First 8+ characters of instinct ID

    Returns:
        Confirmation message
    """
    storage = get_instinct_storage()

    # Find full ID including disabled ones
    all_instincts = storage.list_instincts(status="enabled")
    all_instincts.extend(storage.list_instincts(status="disabled"))

    full_id = None
    for inst in all_instincts:
        if inst["id"].startswith(instinct_id):
            full_id = inst["id"]
            break

    if not full_id:
        return f"Instinct not found: {instinct_id}"

    success = storage.set_instinct_status(full_id, "enabled")

    if success:
        return f"Instinct {instinct_id[:8]}... enabled"

    return f"Failed to enable instinct: {instinct_id}"


@tool
def evolve_instincts() -> str:
    """
    Evolve learned instincts into draft skills.

    This analyzes all learned instincts and groups them into coherent workflows
    that can be saved as skills. Requires human approval via approve_evolved_skill.

    Returns:
        Summary of draft skills generated

    Examples:
        >>> evolve_instincts()
        "Generated 2 draft skills:\\n- Response Style Guide: concise (0.8)\\n- ..."
    """
    from executive_assistant.instincts.evolver import get_instinct_evolver
    from executive_assistant.storage.file_sandbox import get_thread_id

    evolver = get_instinct_evolver()
    thread_id = get_thread_id()

    drafts = evolver.evolve_instincts(thread_id)

    if not drafts:
        return "No suitable instinct clusters found. Need at least 2 related instincts with confidence ≥0.6."

    lines = [f"Generated {len(drafts)} draft skills:"]

    for draft in drafts:
        lines.append(
            f"- {draft['name']}\n"
            f"  Instincts: {len(draft['cluster']['instincts'])}\n"
            f"  Avg confidence: {draft['cluster']['avg_confidence']:.1%}\n"
            f"  Draft ID: {draft['id']}"
        )

    lines.append("\nTo approve a skill, use approve_evolved_skill with the draft ID.")

    return "\n".join(lines)


@tool
def approve_evolved_skill(draft_id: str) -> str:
    """
    Approve a draft skill and save it as a user skill.

    Args:
        draft_id: The draft skill ID from evolve_instincts

    Returns:
        Confirmation message

    Examples:
        >>> approve_evolved_skill("communication_concise_123")
        "Skill 'Response Style Guide: Concise' saved successfully!"
    """
    from executive_assistant.instincts.evolver import get_instinct_evolver
    from executive_assistant.storage.file_sandbox import get_thread_id

    evolver = get_instinct_evolver()
    thread_id = get_thread_id()

    success = evolver.approve_skill(draft_id, thread_id)

    if success:
        return f"Draft skill '{draft_id}' approved and saved as a user skill!"

    return f"Failed to approve draft skill: {draft_id}"


@tool
def export_instincts() -> str:
    """
    Export all instincts as JSON for backup or sharing.

    Returns:
        JSON string of all instincts
    """
    from executive_assistant.storage.file_sandbox import get_thread_id

    storage = get_instinct_storage()
    thread_id = get_thread_id()

    instincts = storage.list_instincts(status=None, thread_id=thread_id)

    export_data = {
        "exported_at": _utc_now(),
        "thread_id": thread_id,
        "instincts": instincts,
    }

    return json.dumps(export_data, indent=2)


@tool
def import_instincts(json_data: str) -> str:
    """
    Import instincts from JSON (exported from another thread/user).

    Args:
        json_data: JSON string of instincts (from export_instincts)

    Returns:
        Confirmation message

    Examples:
        >>> import_instincts('{"instincts": [...]}')
        "Imported 3 instincts successfully"
    """
    try:
        data = json.loads(json_data)

        if "instincts" not in data:
            return "Invalid JSON format. Expected {'instincts': [...]}"

        imported = 0
        for instinct_data in data["instincts"]:
            storage = get_instinct_storage()

            # Create new instinct with same properties but new ID
            new_id = storage.create_instinct(
                trigger=instinct_data["trigger"],
                action=instinct_data["action"],
                domain=instinct_data["domain"],
                source="import",
                confidence=instinct_data.get("confidence", 0.5),
            )

            imported += 1

        return f"Imported {imported} instincts successfully."

    except json.JSONDecodeError:
        return "Invalid JSON format."
    except Exception as e:
        return f"Failed to import instincts: {str(e)}"


@tool
def list_profiles() -> str:
    """
    List all available profile presets.

    Profiles are pre-configured instinct packs for common personality types.

    Returns:
        Formatted list of available profiles

    Examples:
        >>> list_profiles()
        "Available Profiles:\\n- concise_professional: Brief, business-focused...\\n-..."
    """
    from executive_assistant.instincts.profiles import get_profile_manager

    manager = get_profile_manager()
    profiles = manager.list_profiles()

    if not profiles:
        return "No profiles available."

    lines = ["Available Profiles:"]
    for profile in profiles:
        lines.append(
            f"- {profile['id']}: {profile['name']}\n"
            f"  Description: {profile['description']}\n"
            f"  Instincts: {profile['instinct_count']}"
        )

    return "\n".join(lines)


@tool
def apply_profile(
    profile_id: str,
    clear_existing: bool = False,
) -> str:
    """
    Apply a profile preset to the current thread.

    Profiles create a set of pre-configured instincts for common personality types.

    Args:
        profile_id: Profile identifier (e.g., "concise_professional", "detailed_explainer",
                   "friendly_casual", "technical_expert", "agile_developer", "analyst_researcher")
        clear_existing: Whether to disable existing instincts before applying (default False)

    Returns:
        Confirmation message with results

    Examples:
        >>> apply_profile("concise_professional")
        "Profile 'Concise Professional' applied! Created 3 instincts."

        >>> apply_profile("technical_expert", clear_existing=True)
        "Profile 'Technical Expert' applied! Cleared existing instincts, created 4 new instincts."
    """
    from executive_assistant.instincts.profiles import get_profile_manager
    from executive_assistant.storage.file_sandbox import get_thread_id

    manager = get_profile_manager()
    thread_id = get_thread_id()

    result = manager.apply_profile(profile_id, thread_id, clear_existing)

    if result["success"]:
        message = f"Profile '{result['profile']}' applied successfully!\n"
        message += f"Created {result['instincts_created']} instincts.\n"
        message += f"Instinct IDs: {', '.join(result['instinct_ids'])}"
        return message

    return f"Failed to apply profile: {result.get('error', 'Unknown error')}"


@tool
def create_custom_profile(
    name: str,
    description: str,
    instincts_json: str,
) -> str:
    """
    Create and apply a custom profile with specified instincts.

    Args:
        name: Profile name
        description: Profile description
        instincts_json: JSON array of instinct definitions, e.g.:
                       [{"trigger": "...", "action": "...", "domain": "...", "confidence": 0.8}]

    Returns:
        Confirmation message

    Examples:
        >>> create_custom_profile(
        ...     "My Profile",
        ...     "Custom settings",
        ...     '[{"trigger": "user asks", "action": "be brief", "domain": "communication", "confidence": 0.8}]'
        ... )
        "Custom profile 'My Profile' applied! Created 1 instinct."
    """
    from executive_assistant.instincts.profiles import get_profile_manager
    from executive_assistant.storage.file_sandbox import get_thread_id

    try:
        instincts = json.loads(instincts_json)
    except json.JSONDecodeError:
        return "Invalid JSON format for instincts."

    manager = get_profile_manager()
    thread_id = get_thread_id()

    result = manager.create_custom_profile(name, description, instincts, thread_id)

    if result["success"]:
        return f"Custom profile '{result['profile']}' applied! Created {result['instincts_created']} instincts."

    return f"Failed to create custom profile: {result.get('error', 'Unknown error')}"


def get_instinct_tools() -> list:
    """Get all instinct tools for the agent."""
    return [
        create_instinct,
        list_instincts,
        adjust_instinct_confidence,
        get_applicable_instincts,
        disable_instinct,
        enable_instinct,
        evolve_instincts,
        approve_evolved_skill,
        export_instincts,
        import_instincts,
        list_profiles,
        apply_profile,
        create_custom_profile,
    ]
