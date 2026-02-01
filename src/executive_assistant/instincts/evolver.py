"""Instinct evolver for clustering related instincts into skills.

The evolver analyzes learned instincts and groups them into coherent workflows
that can be saved as skills. This requires human-in-the-loop approval.
"""

import json
from datetime import datetime, timezone
from typing import Any, List

from executive_assistant.storage.instinct_storage import get_instinct_storage
from executive_assistant.storage.file_sandbox import get_thread_id


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class InstinctEvolver:
    """Evolver for clustering instincts into draft skills."""

    # Domain mapping for skill suggestions
    DOMAIN_SKILL_MAP = {
        "communication": "Response Style Guide",
        "format": "Output Format Preferences",
        "workflow": "Workflow Patterns",
        "tool_selection": "Tool Selection Preferences",
        "verification": "Quality Verification Standards",
        "timing": "Timing and Scheduling Preferences",
    }

    def __init__(self) -> None:
        self.storage = get_instinct_storage()
        self._drafts_cache: dict[str, dict] = {}  # Cache drafts by thread_id

    def analyze_clusters(
        self,
        thread_id: str | None = None,
    ) -> List[dict[str, Any]]:
        """
        Analyze instincts to find potential clusters.

        Args:
            thread_id: Thread identifier

        Returns:
            List of potential skill clusters
        """
        instincts = self.storage.list_instincts(
            min_confidence=0.5,
            thread_id=thread_id,
        )

        if len(instincts) < 2:
            return []

        # Group by domain
        by_domain = {}
        for instinct in instincts:
            domain = instinct["domain"]
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(instinct)

        # Find clusters within each domain
        clusters = []

        for domain, domain_instincts in by_domain.items():
            if len(domain_instincts) >= 2:
                # Check if instincts are related
                cluster = self._find_cluster(domain_instincts, domain)
                if cluster:
                    clusters.append(cluster)

        return clusters

    def _find_cluster(self, instincts: List[dict], domain: str) -> dict | None:
        """
        Find a cluster of related instincts.

        Simple implementation: groups instincts by keyword similarity in triggers.
        """
        # Extract keywords from triggers
        trigger_words = set()
        for instinct in instincts:
            words = set(instinct["trigger"].lower().split())
            trigger_words.update(words)

        # Filter to meaningful words
        meaningful_words = {w for w in trigger_words if len(w) > 3}

        if not meaningful_words:
            return None

        # Check for common themes
        themes = {}
        for word in meaningful_words:
            count = sum(1 for inst in instincts if word in inst["trigger"].lower())
            if count >= 2:
                themes[word] = count

        if not themes:
            return None

        # Build cluster
        theme_list = list(themes.keys())
        cluster_id = f"{domain}_{max(themes.keys(), key=themes.get)}"

        return {
            "id": cluster_id,
            "domain": domain,
            "instincts": instincts,
            "themes": theme_list,
            "avg_confidence": sum(inst["confidence"] for inst in instincts) / len(instincts),
            "suggested_name": self._suggest_skill_name(domain, theme_list),
        }

    def _suggest_skill_name(self, domain: str, themes: List[str]) -> str:
        """Suggest a skill name based on domain and themes."""
        domain_name = self.DOMAIN_SKILL_MAP.get(domain, domain.title())

        if themes:
            theme_name = themes[0].title()
            return f"{domain_name}: {theme_name}"

        return domain_name

    def generate_draft_skill(
        self,
        cluster: dict,
        thread_id: str | None = None,
    ) -> dict:
        """
        Generate a draft skill from a cluster of instincts.

        Args:
            cluster: Cluster information from analyze_clusters
            thread_id: Thread identifier

        Returns:
            Draft skill content
        """
        instincts = cluster["instincts"]

        # Build skill content
        skill_name = cluster["suggested_name"]

        # Overview
        overview = f"This skill captures behavioral patterns related to {cluster['domain']}.\n\n"
        overview += f"Automatically evolved from {len(instincts)} instincts with {cluster['avg_confidence']:.1%} average confidence.\n"

        # Behavioral patterns section
        patterns = "## Behavioral Patterns\n\n"
        for i, instinct in enumerate(instincts, 1):
            patterns += f"{i}. **{instinct['trigger']}**\n"
            patterns += f"   - Action: {instinct['action']}\n"
            patterns += f"   - Confidence: {instinct['confidence']:.1%}\n"
            patterns += f"   - Source: {instinct['source']}\n\n"

        # Instructions
        instructions = "## Guidelines\n\n"
        instructions += "Apply these patterns in your responses:\n\n"

        domain_guidance = {
            "communication": "Adjust your response style and verbosity based on user preferences.",
            "format": "Structure your output using the user's preferred format.",
            "workflow": "Follow the established workflow patterns the user prefers.",
            "tool_selection": "Prioritize tools that the user consistently prefers.",
            "verification": "Apply the quality standards the user expects.",
            "timing": "Be aware of the user's timing and scheduling preferences.",
        }

        instructions += domain_guidance.get(cluster["domain"], "Follow these patterns.")

        # Examples
        examples = "## Example Applications\n\n"
        examples += "When you observe these triggers, apply the corresponding actions:\n\n"
        for instinct in instincts[:3]:  # Limit to 3 examples
            examples += f"- **Trigger**: {instinct['trigger']}\n"
            examples += f"  **Response**: {instinct['action']}\n\n"

        # Full skill content
        content = f"""# {skill_name}

Description: Auto-generated skill from learned behavioral patterns

Tags: evolved, instinct-cluster, {cluster['domain']}

*Generated: {_utc_now()}*

{overview}

{patterns}

{instructions}

{examples}
"""

        return {
            "id": str(cluster["id"]),
            "name": skill_name,
            "content": content,
            "cluster": cluster,
            "status": "draft",
        }

    def evolve_instincts(
        self,
        thread_id: str | None = None,
    ) -> List[dict]:
        """
        Evolve instincts into draft skills.

        Args:
            thread_id: Thread identifier

        Returns:
            List of draft skills generated
        """
        clusters = self.analyze_clusters(thread_id)

        drafts = []
        for cluster in clusters:
            # Only generate skills for high-confidence clusters
            if cluster["avg_confidence"] >= 0.6:
                draft = self.generate_draft_skill(cluster, thread_id)
                drafts.append(draft)

        # Cache drafts for approval
        if thread_id:
            self._drafts_cache[thread_id] = {d["id"]: d for d in drafts}

        return drafts

    def approve_skill(
        self,
        draft_id: str,
        thread_id: str | None = None,
    ) -> bool:
        """
        Approve a draft skill and save it as a user skill.

        Args:
            draft_id: Draft skill ID
            thread_id: Thread identifier

        Returns:
            True if successful, False otherwise
        """
        # Import here to avoid circular dependency
        from executive_assistant.skills.user_tools import _save_user_skill_file
        import logging

        logger = logging.getLogger(__name__)

        if not thread_id:
            logger.debug(f"[approve_skill] No thread_id provided")
            return False

        # Get cached drafts for this thread
        thread_drafts = self._drafts_cache.get(thread_id, {})

        logger.debug(f"[approve_skill] thread_id={thread_id}")
        logger.debug(f"[approve_skill] Cached thread_ids: {list(self._drafts_cache.keys())}")
        logger.debug(f"[approve_skill] Draft IDs in cache: {list(thread_drafts.keys())}")
        logger.debug(f"[approve_skill] Looking for draft_id: {draft_id}")

        if draft_id not in thread_drafts:
            logger.debug(f"[approve_skill] Draft {draft_id} not found in cache")
            return False

        draft = thread_drafts[draft_id]
        logger.debug(f"[approve_skill] Found draft: {draft.get('name')}")

        # Save as user skill using helper function
        skill_name = draft["name"].lower().replace(" ", "_").replace(":", "")

        result = _save_user_skill_file(
            name=skill_name,
            description=f"Auto-generated from {len(draft['cluster']['instincts'])} instincts",
            content=draft["content"],
            tags=["evolved", "instinct-cluster", draft["cluster"]["domain"]],
        )

        logger.debug(f"[approve_skill] Save result: {result}")

        # Clear cache after approval
        self._drafts_cache.pop(thread_id, None)

        # Check for success
        return "created" in result.lower() or "saved" in result.lower() or "✅" in result


_instinct_evolver = InstinctEvolver()


def get_instinct_evolver() -> InstinctEvolver:
    return _instinct_evolver
