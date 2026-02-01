"""Instinct injector for loading learned behavioral patterns into system prompts.

The injector retrieves applicable instincts for the current context and formats
them for injection into the agent's system prompt between BASE_PROMPT and CHANNEL_APPENDIX.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from executive_assistant.storage.instinct_storage import get_instinct_storage

logger = logging.getLogger(__name__)


class InstinctInjector:
    """Injector for loading applicable instincts into system prompts."""

    # Conflict resolution rules: (domain, action_keyword) -> overrides
    CONFLICT_RESOLUTION = {
        # High-priority overrides
        ("timing", "urgent"): {
            "overrides": [
                ("communication", "detailed"),
                ("communication", "thorough"),
                ("communication", "explain"),
                ("learning_style", "explain"),
            ],
            "min_confidence": 0.6,
        },
        ("communication", "concise"): {
            "overrides": [
                ("communication", "detailed"),
                ("communication", "elaborate"),
                ("communication", "thorough"),
            ],
            "min_confidence": 0.6,
        },
        ("communication", "brief"): {
            "overrides": [
                ("communication", "detailed"),
                ("communication", "elaborate"),
            ],
            "min_confidence": 0.6,
        },
        ("emotional_state", "frustrated"): {
            "overrides": [
                ("workflow", "standard"),
                ("communication", "brief"),
            ],
            "min_confidence": 0.5,  # Lower threshold for emotional state
        },
        ("emotional_state", "confused"): {
            "overrides": [
                ("communication", "brief"),
                ("communication", "concise"),
            ],
            "min_confidence": 0.5,
        },
    }

    # Domain-specific guidance templates
    DOMAIN_TEMPLATES = {
        "communication": "## Communication Style\n{actions}\n",
        "format": "## Output Format Preferences\n{actions}\n",
        "workflow": "## Workflow Patterns\n{actions}\n",
        "tool_selection": "## Tool Selection Preferences\n{actions}\n",
        "verification": "## Quality Standards\n{actions}\n",
        "timing": "## Timing Preferences\n{actions}\n",
        # NEW domains
        "emotional_state": """## Emotional Context
The user appears to be in the following emotional state:
{actions}

Adjust your response accordingly:
- Be extra supportive and patient
- Offer to break down complex tasks
- Provide alternative approaches
""",
        "learning_style": """## Learning Approach
Based on past interactions, the user prefers:
{actions}

Adapt your explanations:
- Teaching mode: Show reasoning, offer resources
- Exploration mode: Provide options, explain trade-offs
- Hands-on mode: Focus on practical implementation
""",
        "expertise": """## Known Expertise Areas
The user has demonstrated knowledge in:
{actions}

Adjust your explanations:
- Skip basics in known areas
- Provide context for new topics
- Assume familiarity with domain terminology
""",
    }

    def __init__(self) -> None:
        self.storage = get_instinct_storage()

    def _resolve_conflicts(self, instincts: list[dict]) -> list[dict]:
        """Remove overridden instincts based on priority rules.

        Args:
            instincts: List of instinct dictionaries

        Returns:
            Filtered list with conflicts resolved
        """
        kept = []
        removed_count = 0

        for instinct in instincts:
            domain = instinct["domain"]
            action = instinct["action"].lower()
            confidence = instinct["confidence"]

            # Check if this instinct should be kept or overridden
            should_keep = True
            override_reason = None

            for kept_instinct in kept:
                # Check if any kept instinct overrides the current one
                for (rule_domain, rule_action), rule in self.CONFLICT_RESOLUTION.items():
                    # Does the kept instinct match a rule?
                    if (kept_instinct["domain"] == rule_domain and
                            rule_action in kept_instinct["action"].lower() and
                            kept_instinct["confidence"] >= rule["min_confidence"]):

                        # Check if current instinct is in the override list
                        for override_domain, override_action in rule["overrides"]:
                            if (domain == override_domain and
                                    override_action in action):

                                should_keep = False
                                override_reason = (
                                    f"Overridden by {rule_domain}:{rule_action} "
                                    f"(confidence: {kept_instinct['confidence']:.2f})"
                                )
                                break

                        if not should_keep:
                            break

                if not should_keep:
                    break

            if should_keep:
                kept.append(instinct)
            else:
                logger.debug(f"Conflict resolution: {override_reason} | Removed: {instinct['action'][:50]}")
                removed_count += 1

        if removed_count > 0:
            logger.info(f"Conflict resolution removed {removed_count} contradictory instincts")

        return kept

    def build_instincts_context(
        self,
        thread_id: str,
        user_message: str | None = None,
        min_confidence: float = 0.5,
        max_per_domain: int = None,  # None = adaptive
    ) -> str:
        """
        Build instincts section for system prompt.

        Args:
            thread_id: Thread identifier
            user_message: Current user message for context filtering (optional)
            min_confidence: Minimum confidence threshold (default 0.5)
            max_per_domain: Maximum instincts to include per domain (default 3, None=adaptive)

        Returns:
            Formatted instincts section for injection into system prompt
        """
        # Adaptive max_per_domain calculation
        if max_per_domain is None:
            # We'll calculate after loading instincts (O(n) but n is small)
            adaptive_mode = True
        else:
            adaptive_mode = False

        # Get applicable instincts
        if user_message:
            # Context-aware: get instincts matching current situation
            # Use large limit for adaptive mode, calculate specific limit otherwise
            limit = max_per_domain * 6 if max_per_domain is not None else 100
            instincts = self.storage.get_applicable_instincts(
                context=user_message,
                thread_id=thread_id,
                max_count=limit,  # Get more, then filter by domain
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

        # Apply comprehensive metadata-based confidence adjustments
        scored_instincts = []
        now = datetime.now(timezone.utc)

        for instinct in instincts:
            base_confidence = instinct["confidence"]
            metadata = instinct.get("metadata", {})

            # Factor 1: Occurrence count (frequency)
            occurrence_count = metadata.get("occurrence_count", 0)
            frequency_boost = min(0.15, occurrence_count * 0.03)

            # Factor 2: Recency (staleness penalty)
            last_triggered_str = metadata.get("last_triggered")
            if last_triggered_str:
                try:
                    last_triggered = datetime.fromisoformat(last_triggered_str)
                    days_since_trigger = (now - last_triggered).days
                    staleness_penalty = max(-0.2, -days_since_trigger * 0.01)
                except Exception:
                    staleness_penalty = -0.1  # Unable to parse
            else:
                staleness_penalty = -0.1  # Never triggered

            # Factor 3: Success rate
            success_rate = metadata.get("success_rate", 1.0)
            success_multiplier = max(0.8, success_rate)

            # Combine factors
            final_confidence = base_confidence + frequency_boost + staleness_penalty
            final_confidence *= success_multiplier
            final_confidence = max(0.0, min(1.0, final_confidence))

            # Store breakdown for debugging
            instinct["final_confidence"] = final_confidence
            instinct["confidence_breakdown"] = {
                "base": base_confidence,
                "frequency_boost": frequency_boost,
                "staleness_penalty": staleness_penalty,
                "success_multiplier": success_multiplier,
            }

            scored_instincts.append(instinct)

            # Log significant adjustments
            if abs(final_confidence - base_confidence) > 0.1:
                logger.debug(
                    f"Confidence adjustment: {base_confidence:.2f} → {final_confidence:.2f} "
                    f"(freq:+{frequency_boost:.2f}, staleness:{staleness_penalty:.2f}, "
                    f"success:{success_multiplier:.2f}) | {instinct['action'][:50]}"
                )

        # Filter by final confidence
        instincts = [i for i in scored_instincts if i["final_confidence"] >= min_confidence]

        # Adaptive max_per_domain calculation
        if adaptive_mode and instincts:
            # Calculate average confidence of all scored instincts
            avg_confidence = sum(i["final_confidence"] for i in scored_instincts) / len(scored_instincts)

            # Set max_per_domain based on quality thresholds
            if avg_confidence > 0.8:
                max_per_domain = 5  # High quality: include more instincts
            elif avg_confidence > 0.6:
                max_per_domain = 3  # Medium quality: standard limit
            else:
                max_per_domain = 1  # Lower quality: be conservative

            logger.debug(
                f"Adaptive injection: avg_confidence={avg_confidence:.2f} → max_per_domain={max_per_domain}"
            )
        elif not instincts:
            max_per_domain = 0  # No instincts to include

        # Sort by final confidence
        instincts.sort(key=lambda i: i["final_confidence"], reverse=True)

        # Resolve conflicts: remove contradictory instincts
        instincts = self._resolve_conflicts(instincts)

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

    def format_instincts_for_user(
        self,
        thread_id: str,
        min_confidence: float = 0.5,
    ) -> str:
        """
        Format learned instincts in user-friendly language.

        Shows what the agent has learned about the user's preferences.

        Args:
            thread_id: Thread identifier
            min_confidence: Minimum confidence threshold

        Returns:
            User-friendly formatted text describing learned patterns
        """
        instincts = self.storage.list_instincts(
            min_confidence=min_confidence,
            thread_id=thread_id,
        )

        if not instincts:
            return "I haven't learned your preferences yet. As we interact more, I'll adapt to your communication style and preferences."

        # Sort by confidence descending
        instincts.sort(key=lambda i: i["confidence"], reverse=True)

        # Group by domain
        by_domain: dict[str, list[dict]] = {}
        for instinct in instincts:
            domain = instinct["domain"]
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(instinct)

        # Build user-friendly output
        sections = []
        sections.append("## What I've Learned About Your Preferences")
        sections.append("")
        sections.append(
            f"Based on our interactions, I've noticed {len(instincts)} patterns "
            f"in how you prefer to work:"
        )
        sections.append("")

        # Format each domain
        for domain in sorted(by_domain.keys()):
            domain_instincts = by_domain[domain]

            # User-friendly domain names
            domain_names = {
                "communication": "Communication Style",
                "format": "Output Format",
                "workflow": "Workflow",
                "tool_selection": "Tool Preferences",
                "verification": "Quality Standards",
                "timing": "Timing",
                "emotional_state": "Emotional Patterns",
                "learning_style": "Learning Style",
                "expertise": "Your Expertise",
            }

            domain_title = domain_names.get(domain, domain.replace("_", " ").title())
            sections.append(f"### {domain_title}")
            sections.append("")

            for instinct in domain_instincts:
                confidence = instinct["confidence"]
                action = instinct["action"]
                trigger = instinct["trigger"]
                metadata = instinct.get("metadata", {})

                # Confidence indicator
                if confidence >= 0.9:
                    strength = "Always"
                elif confidence >= 0.75:
                    strength = "Usually"
                elif confidence >= 0.6:
                    strength = "Often"
                else:
                    strength = "Sometimes"

                # Format the instinct
                sections.append(f"**{strength}**: {action}")

                # Add trigger context for lower-confidence instincts
                if confidence < 0.75:
                    sections.append(f"_When: {trigger}_")

                # Add metadata for transparency
                occurrence_count = metadata.get("occurrence_count", 0)
                if occurrence_count > 0:
                    sections.append(f"_(Seen {occurrence_count} times)_")

                sections.append("")

        # Add learning note
        sections.append("---")
        sections.append("")
        sections.append(
            "*I continuously learn from our interactions. If something here is wrong, "
            "just let me know and I'll adjust!*"
        )

        return "\n".join(sections)


_instinct_injector = InstinctInjector()


def get_instinct_injector() -> InstinctInjector:
    """Get singleton instinct injector instance."""
    return _instinct_injector
