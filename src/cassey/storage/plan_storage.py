"""Plan storage for thread-scoped planning files.

Each thread has its own plan directory under data/users/{thread_id}/plan/ with:
- task_plan.md: The main task plan with phases, decisions, errors
- findings.md: Research findings and technical decisions
- progress.md: Session log, test results, error log
- archive/: Completed plans from previous tasks

This is strictly separated from user files - plan tools access this directory,
while standard file tools do not.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path

from cassey.config.settings import settings
from cassey.storage.file_sandbox import get_thread_id


# Plan templates embedded as strings
TASK_PLAN_TEMPLATE = """# Task Plan: [Brief Description]
<!--
  WHAT: This is your roadmap for the entire task. Think of it as your "working memory on disk."
  WHY: After 50+ tool calls, your original goals can get forgotten. This file keeps them fresh.
  WHEN: Create this FIRST, before starting any work. Update after each phase completes.
-->

## Goal
<!--
  WHAT: One clear sentence describing what you're trying to achieve.
  WHY: This is your north star. Re-reading this keeps you focused on the end state.
  EXAMPLE: "Create a Python CLI todo app with add, list, and delete functionality."
-->
[One sentence describing the end state]

## Current Phase
<!--
  WHAT: Which phase you're currently working on (e.g., "Phase 1", "Phase 3").
  WHY: Quick reference for where you are in the task. Update this as you progress.
-->
Phase 1

## Phases
<!--
  WHAT: Break your task into 3-7 logical phases. Each phase should be completable.
  WHY: Breaking work into phases prevents overwhelm and makes progress visible.
  WHEN: Update status after completing each phase: pending → in_progress → complete
-->

### Phase 1: Requirements & Discovery
<!--
  WHAT: Understand what needs to be done and gather initial information.
  WHY: Starting without understanding leads to wasted effort. This phase prevents that.
-->
- [ ] Understand user intent
- [ ] Identify constraints and requirements
- [ ] Document findings in findings.md
- **Status:** in_progress

### Phase 2: Planning & Structure
<!--
  WHAT: Decide how you'll approach the problem and what structure you'll use.
  WHY: Good planning prevents rework. Document decisions so you remember why you chose them.
-->
- [ ] Define technical approach
- [ ] Create project structure if needed
- [ ] Document decisions with rationale
- **Status:** pending

### Phase 3: Implementation
<!--
  WHAT: Actually build/create/write the solution.
  WHY: This is where the work happens. Break into smaller sub-tasks if needed.
-->
- [ ] Execute the plan step by step
- [ ] Write code to files before executing
- [ ] Test incrementally
- **Status:** pending

### Phase 4: Testing & Verification
<!--
  WHAT: Verify everything works and meets requirements.
  WHY: Catching issues early saves time. Document test results in progress.md.
-->
- [ ] Verify all requirements met
- [ ] Document test results in progress.md
- [ ] Fix any issues found
- **Status:** pending

### Phase 5: Delivery
<!--
  WHAT: Final review and handoff to user.
  WHY: Ensures nothing is forgotten and deliverables are complete.
-->
- [ ] Review all output files
- [ ] Ensure deliverables are complete
- [ ] Deliver to user
- **Status:** pending

## Key Questions
<!--
  WHAT: Important questions you need to answer during the task.
  WHY: These guide your research and decision-making. Answer them as you go.
-->
1. [Question to answer]
2. [Question to answer]

## Decisions Made
<!--
  WHAT: Technical and design decisions you've made, with the reasoning behind them.
  WHY: You'll forget why you made choices. This table helps you remember and justify decisions.
-->
| Decision | Rationale |
|----------|-----------|
|          |           |

## Errors Encountered
<!--
  WHAT: Every error you encounter, what attempt number it was, and how you resolved it.
  WHY: Logging errors prevents repeating the same mistakes.
-->
| Error | Attempt | Resolution |
|-------|---------|------------|
|       | 1       |            |

## Notes
- Update phase status as you progress: pending → in_progress → complete
- Re-read this plan before major decisions
- Log ALL errors - they help avoid repetition
"""

FINDINGS_TEMPLATE = """# Findings & Decisions
<!--
  WHAT: Your knowledge base for the task. Stores everything you discover and decide.
  WHY: Context windows are limited. This file is your "external memory" - persistent and unlimited.
  WHEN: Update after ANY discovery, especially after 2 view/browser/search operations.
-->

## Requirements
<!--
  WHAT: What the user asked for, broken down into specific requirements.
-->
-
-

## Research Findings
<!--
  WHAT: Key discoveries from web searches, documentation reading, or exploration.
  WHY: Multimodal content doesn't persist. Write it down immediately.
-->
-
-

## Technical Decisions
<!--
  WHAT: Architecture and implementation choices you've made, with reasoning.
-->
| Decision | Rationale |
|----------|-----------|
|          |           |

## Issues Encountered
<!--
  WHAT: Problems you ran into and how you solved them.
-->
| Issue | Resolution |
|-------|------------|
|       |            |

## Resources
<!--
  WHAT: URLs, file paths, API references, documentation links.
-->
-
-

## Visual/Browser Findings
<!--
  WHAT: Information you learned from viewing images, PDFs, or browser results.
  WHY: CRITICAL - Visual/multimodal content doesn't persist in context.
-->
-
-
"""

PROGRESS_TEMPLATE = """# Progress Log
<!--
  WHAT: Your session log - a chronological record of what you did, when, and what happened.
-->

## Session: [DATE]
-

### Phase 1: [Title]
- **Status:** in_progress
- **Started:** [timestamp]
- Actions taken:
  -
- Files created/modified:
  -

### Phase 2: [Title]
- **Status:** pending
- Actions taken:
  -
- Files created/modified:
  -

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
|      |       |          |        |        |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
|           |       | 1       |            |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase X |
| Where am I going? | Remaining phases |
| What's the goal? | [goal statement] |
| What have I learned? | See findings.md |
| What have I done? | See above |
"""


class PlanStorage:
    """
    Plan storage for thread-scoped planning files.

    Plan files are stored under data/users/{thread_id}/plan/ and are:
    - Separate from user files (not visible via list_files, etc.)
    - Only accessible via plan tools
    - Used for multi-step task tracking
    """

    def __init__(self) -> None:
        """Initialize plan storage."""

    def _get_plan_dir(self, thread_id: str | None = None) -> Path:
        """
        Get the plan directory for a thread.

        Args:
            thread_id: Thread identifier. If None, uses current context thread_id.

        Returns:
            Path to the plan directory.
        """
        if thread_id is None:
            thread_id = get_thread_id()

        if thread_id is None:
            raise ValueError("No thread_id provided and no thread_id in context")

        plan_dir = settings.get_thread_plan_path(thread_id)
        plan_dir.mkdir(parents=True, exist_ok=True)

        # Create archive subdir
        archive_dir = plan_dir / "archive"
        archive_dir.mkdir(exist_ok=True)

        return plan_dir

    def get_archive_dir(self, thread_id: str | None = None) -> Path:
        """
        Get the archive directory for a thread.

        Args:
            thread_id: Thread identifier. If None, uses current context thread_id.

        Returns:
            Path to the archive directory.
        """
        plan_dir = self._get_plan_dir(thread_id)
        return plan_dir / "archive"

    def initialize_plan(
        self,
        task_title: str,
        thread_id: str | None = None,
        force_new: bool = False,
    ) -> dict[str, str]:
        """
        Initialize a new plan from templates.

        Args:
            task_title: Brief description of the task.
            thread_id: Thread identifier (uses context if None).
            force_new: If True, overwrite existing plan files.

        Returns:
            Dict with keys: task_plan, findings, progress (file paths created)
        """
        plan_dir = self._get_plan_dir(thread_id)

        task_plan_path = plan_dir / "task_plan.md"
        findings_path = plan_dir / "findings.md"
        progress_path = plan_dir / "progress.md"

        # Check if plan already exists
        if not force_new and task_plan_path.exists():
            # Check if completed
            if self._is_plan_completed(task_plan_path):
                # Archive existing plan
                self._archive_plan(thread_id)
            else:
                # Existing active plan - return paths
                return {
                    "task_plan": str(task_plan_path),
                    "findings": str(findings_path),
                    "progress": str(progress_path),
                    "status": "existing",
                }

        # Create from templates
        task_plan_content = TASK_PLAN_TEMPLATE.replace(
            "[Brief Description]", task_title
        )
        task_plan_content = task_plan_content.replace(
            "[One sentence describing the end state]", task_title
        )

        findings_content = FINDINGS_TEMPLATE
        progress_content = PROGRESS_TEMPLATE.replace("[DATE]", datetime.now().strftime("%Y-%m-%d"))

        task_plan_path.write_text(task_plan_content)
        findings_path.write_text(findings_content)
        progress_path.write_text(progress_content)

        return {
            "task_plan": str(task_plan_path),
            "findings": str(findings_path),
            "progress": str(progress_path),
            "status": "created",
        }

    def _is_plan_completed(self, task_plan_path: Path) -> bool:
        """
        Check if a plan is marked as completed.

        Args:
            task_plan_path: Path to task_plan.md

        Returns:
            True if plan is completed, False otherwise
        """
        if not task_plan_path.exists():
            return False

        content = task_plan_path.read_text()

        # Check for Status: complete (case-insensitive)
        if re.search(r"Status:\s*complete", content, re.IGNORECASE):
            return True

        # Check if all phases are marked complete
        phases = re.findall(r"### Phase \d+:.*?\*\*Status:\*\*\s*(\w+)", content, re.IGNORECASE)
        if phases and all(status.lower() == "complete" for status in phases):
            return True

        return False

    def _archive_plan(self, thread_id: str | None = None) -> str:
        """
        Archive the current plan.

        Args:
            thread_id: Thread identifier (uses context if None).

        Returns:
            Path to the archived plan file.
        """
        plan_dir = self._get_plan_dir(thread_id)
        archive_dir = self.get_archive_dir(thread_id)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        archive_path = archive_dir / f"plan-{timestamp}.md"

        # Merge all plan files into one
        task_plan_path = plan_dir / "task_plan.md"
        findings_path = plan_dir / "findings.md"
        progress_path = plan_dir / "progress.md"

        archive_content = []

        if task_plan_path.exists():
            archive_content.append(task_plan_path.read_text())

        if findings_path.exists():
            archive_content.append("\n\n" + findings_path.read_text())

        if progress_path.exists():
            archive_content.append("\n\n" + progress_path.read_text())

        archive_path.write_text("\n".join(archive_content))

        return str(archive_path)

    def read_plan(
        self,
        which: str = "task_plan",
        thread_id: str | None = None,
    ) -> str:
        """
        Read a plan file.

        Args:
            which: Which plan file to read (task_plan, findings, progress).
            thread_id: Thread identifier (uses context if None).

        Returns:
            File contents.

        Raises:
            FileNotFoundError: If plan file doesn't exist.
        """
        plan_dir = self._get_plan_dir(thread_id)

        filename = f"{which}.md"
        file_path = plan_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"Plan file not found: {filename}")

        return file_path.read_text()

    def write_plan(
        self,
        which: str,
        content: str,
        thread_id: str | None = None,
    ) -> str:
        """
        Write content to a plan file.

        Args:
            which: Which plan file to write (task_plan, findings, progress).
            content: Content to write.
            thread_id: Thread identifier (uses context if None).

        Returns:
            Success message.
        """
        plan_dir = self._get_plan_dir(thread_id)

        filename = f"{which}.md"
        file_path = plan_dir / filename

        file_path.write_text(content)

        return f"Plan file updated: {filename}"

    def update_plan_section(
        self,
        which: str,
        section: str,
        content: str,
        thread_id: str | None = None,
    ) -> str:
        """
        Update a specific section in a plan file.

        Args:
            which: Which plan file to update (task_plan, findings, progress).
            section: Section heading (without ##).
            content: New content for the section.
            thread_id: Thread identifier (uses context if None).

        Returns:
            Success message.
        """
        plan_dir = self._get_plan_dir(thread_id)

        filename = f"{which}.md"
        file_path = plan_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"Plan file not found: {filename}")

        file_content = file_path.read_text()

        # Find and replace the section
        # Pattern: ## Section\n...\n(##|$)
        pattern = rf"(## {re.escape(section)}.*?\n)(.*?)(\n## |\Z)"

        def replacer(match):
            return match.group(1) + content + match.group(3)

        new_content, count = re.subn(pattern, replacer, file_content, flags=re.DOTALL)

        if count == 0:
            # Section not found, append to end
            new_content = file_content.rstrip() + f"\n\n## {section}\n{content}\n"

        file_path.write_text(new_content)

        return f"Section '{section}' updated in {filename}"

    def clear_plan(
        self,
        thread_id: str | None = None,
        confirm: bool = False,
    ) -> str:
        """
        Clear the current plan files.

        Args:
            thread_id: Thread identifier (uses context if None).
            confirm: Must be True to actually clear (safety check).

        Returns:
            Success message or confirmation prompt.
        """
        if not confirm:
            return "To clear the plan, call clear_plan with confirm=True"

        plan_dir = self._get_plan_dir(thread_id)

        for filename in ["task_plan.md", "findings.md", "progress.md"]:
            file_path = plan_dir / filename
            if file_path.exists():
                file_path.unlink()

        return "Plan files cleared (archive preserved)"

    def list_plans(self, thread_id: str | None = None) -> dict:
        """
        List current and archived plans.

        Args:
            thread_id: Thread identifier (uses context if None).

        Returns:
            Dict with current plan status and list of archived plans.
        """
        plan_dir = self._get_plan_dir(thread_id)
        archive_dir = self.get_archive_dir(thread_id)

        task_plan_path = plan_dir / "task_plan.md"

        result = {
            "current": {
                "exists": task_plan_path.exists(),
                "completed": self._is_plan_completed(task_plan_path) if task_plan_path.exists() else False,
            },
            "archived": [],
        }

        # List archived plans
        for archive_file in sorted(archive_dir.glob("plan-*.md"), reverse=True):
            result["archived"].append({
                "filename": archive_file.name,
                "created": datetime.fromtimestamp(archive_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })

        return result


# Global storage instance
_plan_storage = PlanStorage()


def get_plan_storage() -> PlanStorage:
    """Get the global plan storage instance."""
    return _plan_storage
