"""Profile presets for quick personality configuration.

Profile presets are pre-configured instinct packs that users can quickly
apply to set common personality types and communication styles.
"""

from typing import Any


# Profile preset definitions
PROFILE_PRESETS = {
    "concise_professional": {
        "name": "Concise Professional",
        "description": "Brief, business-focused communication with minimal fluff",
        "instincts": [
            {
                "trigger": "user asks any question",
                "action": "respond briefly and professionally, skip detailed explanations",
                "domain": "communication",
                "confidence": 0.85,
            },
            {
                "trigger": "user requests information or report",
                "action": "use bullet points for lists and structured content",
                "domain": "format",
                "confidence": 0.80,
            },
            {
                "trigger": "user gives multi-step task",
                "action": "confirm understanding, proceed without asking unnecessary questions",
                "domain": "workflow",
                "confidence": 0.75,
            },
        ],
    },
    "detailed_explainer": {
        "name": "Detailed Explainer",
        "description": "Thorough explanations with examples and context",
        "instincts": [
            {
                "trigger": "user asks any question",
                "action": "provide comprehensive explanations with examples and context",
                "domain": "communication",
                "confidence": 0.85,
            },
            {
                "trigger": "introducing new concept or topic",
                "action": "explain background and context before answering",
                "domain": "communication",
                "confidence": 0.80,
            },
            {
                "trigger": "user requests information",
                "action": "use structured paragraphs with clear headings",
                "domain": "format",
                "confidence": 0.75,
            },
        ],
    },
    "friendly_casual": {
        "name": "Friendly Casual",
        "description": "Conversational, approachable tone with informal language",
        "instincts": [
            {
                "trigger": "user greets or starts conversation",
                "action": "respond warmly and conversationally",
                "domain": "communication",
                "confidence": 0.85,
            },
            {
                "trigger": "user asks any question",
                "action": "use friendly, approachable language, avoid being overly formal",
                "domain": "communication",
                "confidence": 0.80,
            },
            {
                "trigger": "user shares personal information",
                "action": "acknowledge with empathy and warmth",
                "domain": "communication",
                "confidence": 0.75,
            },
        ],
    },
    "technical_expert": {
        "name": "Technical Expert",
        "description": "Precise technical language with implementation details",
        "instincts": [
            {
                "trigger": "user asks technical question",
                "action": "use precise technical terminology and concepts",
                "domain": "communication",
                "confidence": 0.90,
            },
            {
                "trigger": "user requests implementation or code",
                "action": "provide detailed implementation steps with technical considerations",
                "domain": "workflow",
                "confidence": 0.85,
            },
            {
                "trigger": "explaining technical concept",
                "action": "include technical details, edge cases, and best practices",
                "domain": "communication",
                "confidence": 0.80,
            },
            {
                "trigger": "user requests data export",
                "action": "use JSON or CSV format by default",
                "domain": "format",
                "confidence": 0.85,
            },
        ],
    },
    "agile_developer": {
        "name": "Agile Developer",
        "description": "Practical, iterative approach with testing focus",
        "instincts": [
            {
                "trigger": "user requests implementation",
                "action": "break into small iterative steps, suggest testing",
                "domain": "workflow",
                "confidence": 0.85,
            },
            {
                "trigger": "user asks about code quality",
                "action": "emphasize testing, code review, and refactoring",
                "domain": "communication",
                "confidence": 0.80,
            },
            {
                "trigger": "providing code or implementation",
                "action": "include tests and validation steps",
                "domain": "verification",
                "confidence": 0.85,
            },
        ],
    },
    "analyst_researcher": {
        "name": "Analyst Researcher",
        "description": "Data-driven, thorough analysis with citations",
        "instincts": [
            {
                "trigger": "user asks analytical question",
                "action": "provide thorough analysis with data and evidence",
                "domain": "communication",
                "confidence": 0.85,
            },
            {
                "trigger": "making claims or assertions",
                "action": "provide sources, evidence, or reasoning",
                "domain": "verification",
                "confidence": 0.80,
            },
            {
                "trigger": "user requests data or information",
                "action": "use structured tables or clear organized format",
                "domain": "format",
                "confidence": 0.75,
            },
            {
                "trigger": "analyzing problem or situation",
                "action": "consider multiple perspectives and edge cases",
                "domain": "workflow",
                "confidence": 0.75,
            },
        ],
    },
}


class ProfileManager:
    """Manager for applying profile presets to user threads."""

    def __init__(self) -> None:
        from executive_assistant.storage.instinct_storage import get_instinct_storage

        self.storage = get_instinct_storage()

    def list_profiles(self) -> list[dict[str, Any]]:
        """List all available profile presets."""
        profiles = []
        for profile_id, profile_data in PROFILE_PRESETS.items():
            profiles.append(
                {
                    "id": profile_id,
                    "name": profile_data["name"],
                    "description": profile_data["description"],
                    "instinct_count": len(profile_data["instincts"]),
                }
            )
        return profiles

    def apply_profile(
        self,
        profile_id: str,
        thread_id: str,
        clear_existing: bool = False,
    ) -> dict[str, Any]:
        """
        Apply a profile preset to a thread.

        Args:
            profile_id: Profile identifier (e.g., "concise_professional")
            thread_id: Thread identifier
            clear_existing: Whether to clear existing instincts before applying

        Returns:
            Dictionary with results including created instinct IDs
        """
        if profile_id not in PROFILE_PRESETS:
            return {
                "success": False,
                "error": f"Unknown profile: {profile_id}",
                "available_profiles": list(PROFILE_PRESETS.keys()),
            }

        profile = PROFILE_PRESETS[profile_id]

        # Optionally clear existing instincts
        if clear_existing:
            existing = self.storage.list_instincts(thread_id=thread_id)
            for instinct in existing:
                self.storage.set_instinct_status(instinct["id"], "disabled", thread_id)

        # Create profile instincts
        created_instincts = []
        for instinct_data in profile["instincts"]:
            instinct_id = self.storage.create_instinct(
                trigger=instinct_data["trigger"],
                action=instinct_data["action"],
                domain=instinct_data["domain"],
                source="profile-preset",
                confidence=instinct_data["confidence"],
                thread_id=thread_id,
            )
            created_instincts.append(instinct_id)

        return {
            "success": True,
            "profile": profile["name"],
            "instincts_created": len(created_instincts),
            "instinct_ids": [iid[:8] + "..." for iid in created_instincts],
        }

    def create_custom_profile(
        self,
        name: str,
        description: str,
        instincts: list[dict[str, Any]],
        thread_id: str,
    ) -> dict[str, Any]:
        """
        Create and apply a custom profile.

        Args:
            name: Profile name
            description: Profile description
            instincts: List of instinct definitions
            thread_id: Thread identifier

        Returns:
            Result dictionary
        """
        created_instincts = []

        for instinct_data in instincts:
            required_fields = ["trigger", "action", "domain"]
            if not all(field in instinct_data for field in required_fields):
                return {
                    "success": False,
                    "error": f"Instinct missing required fields: {required_fields}",
                }

            instinct_id = self.storage.create_instinct(
                trigger=instinct_data["trigger"],
                action=instinct_data["action"],
                domain=instinct_data["domain"],
                source="custom-profile",
                confidence=instinct_data.get("confidence", 0.7),
                thread_id=thread_id,
            )
            created_instincts.append(instinct_id)

        return {
            "success": True,
            "profile": name,
            "instincts_created": len(created_instincts),
            "instinct_ids": [iid[:8] + "..." for iid in created_instincts],
        }


_profile_manager = ProfileManager()


def get_profile_manager() -> ProfileManager:
    """Get singleton profile manager instance."""
    return _profile_manager
