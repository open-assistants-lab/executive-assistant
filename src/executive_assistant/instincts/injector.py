"""Instinct injector for loading learned behavioral patterns into system prompts.

The injector retrieves applicable instincts for the current context and formats
them for injection into the agent's system prompt between BASE_PROMPT and CHANNEL_APPENDIX.
"""

from typing import Any

from executive_assistant.storage.instinct_storage import get_instinct_storage


class InstinctInjector:
    """Injector for loading applicable instincts into system prompts."""

    # Domain-specific guidance templates
    DOMAIN_TEMPLATES = {
        "communication": "## Communication Style\n{actions}\n",
        "format": "## Output Format Preferences\n{actions}\n",
        "workflow": "## Workflow Patterns\n{actions}\n",
        "tool_selection": "## Tool Selection Preferences\n{actions}\n",
        "verification": "## Quality Standards\n{actions}\n",
        "timing": "## Timing Preferences\n{actions}\n",
    }

    def __init__(self) -> None:
        self.storage = get_instinct_storage()

    def build_instincts_context(
        self,
        thread_id: str,
        user_message: str | None = None,
        min_confidence: float = 0.5,
        max_per_domain: int = 3,
    ) -> str:
        """
        Build instincts section for system prompt.

        Args:
            thread_id: Thread identifier
            user_message: Current user message for context filtering (optional)
            min_confidence: Minimum confidence threshold (default 0.5)
            max_per_domain: Maximum instincts to include per domain (default 3)

        Returns:
            Formatted instincts section for injection into system prompt
        """
        # Get applicable instincts
        if user_message:
            # Context-aware: get instincts matching current situation
            instincts = self.storage.get_applicable_instincts(
                context=user_message,
                thread_id=thread_id,
                max_count=max_per_domain * 6,  # Get more, then filter by domain
            )
            # Fall back to all high-confidence instincts if no matches
            if not instincts:
                instincts = self.storage.list_instincts(
                    min_confidence=min_confidence,
                    thread_id=thread_id,
                )
        else:
            # Load all high-confidence instincts
            instincts = self.storage.list_instincts(
                min_confidence=min_confidence,
                thread_id=thread_id,
            )

        if not instincts:
            return ""

        # Group by domain
        by_domain: dict[str, list[dict]] = {}
        for instinct in instincts:
            domain = instinct["domain"]
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(instinct)

        # Build context section
        sections = []

        # Add header
        sections.append("## Behavioral Patterns")
        sections.append("")
        sections.append(f"Apply these learned preferences from your interactions:")
        sections.append("")

        # Add domain-specific sections
        for domain in sorted(by_domain.keys()):
            domain_instincts = by_domain[domain][:max_per_domain]

            # Format actions for this domain
            actions = []
            for instinct in domain_instincts:
                confidence = instinct["confidence"]
                trigger = instinct["trigger"]
                action = instinct["action"]

                # Format based on confidence
                if confidence >= 0.8:
                    actions.append(f"- **{action}** (always apply)")
                elif confidence >= 0.6:
                    actions.append(f"- {action}")
                else:
                    actions.append(f"- {action} (when: {trigger})")

            # Add domain section
            domain_name = domain.replace("_", " ").title()
            sections.append(f"### {domain_name}")
            sections.extend(actions)
            sections.append("")

        return "\n".join(sections)

    def get_instincts_summary(
        self,
        thread_id: str,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        """
        Get summary statistics about loaded instincts.

        Args:
            thread_id: Thread identifier
            min_confidence: Minimum confidence threshold

        Returns:
            Dictionary with instinct statistics
        """
        instincts = self.storage.list_instincts(
            min_confidence=min_confidence,
            thread_id=thread_id,
        )

        # Count by domain
        by_domain: dict[str, int] = {}
        total_confidence = 0.0

        for instinct in instincts:
            domain = instinct["domain"]
            by_domain[domain] = by_domain.get(domain, 0) + 1
            total_confidence += instinct["confidence"]

        avg_confidence = total_confidence / len(instincts) if instincts else 0.0

        return {
            "total": len(instincts),
            "by_domain": by_domain,
            "avg_confidence": avg_confidence,
            "min_confidence": min_confidence,
        }


_instinct_injector = InstinctInjector()


def get_instinct_injector() -> InstinctInjector:
    """Get singleton instinct injector instance."""
    return _instinct_injector
