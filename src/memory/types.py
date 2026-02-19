"""Memory types for Executive Assistant."""

from enum import Enum


class MemoryType(str, Enum):
    """Types of memories stored in the system."""

    PROFILE = "profile"  # User profile info (name, role, etc.)
    CONTACT = "contact"  # Contact information
    PREFERENCE = "preference"  # User preferences
    SCHEDULE = "schedule"  # Scheduled events
    TASK = "task"  # Tasks/todos
    DECISION = "decision"  # Decisions made
    INSIGHT = "insight"  # Insights gathered
    CONTEXT = "context"  # Context about projects
    GOAL = "goal"  # Goals and objectives
    CHAT = "chat"  # Chat history summaries
    FEEDBACK = "feedback"  # User feedback
    PERSONAL = "personal"  # Personal information


MEMORY_TYPE_DESCRIPTIONS = {
    MemoryType.PROFILE: "User's professional profile (role, skills, company, etc.)",
    MemoryType.CONTACT: "Contact information for people, organizations",
    MemoryType.PREFERENCE: "User's communication preferences, working style, favorite tools",
    MemoryType.SCHEDULE: "Upcoming meetings, events, deadlines",
    MemoryType.TASK: "Tasks, todos, action items",
    MemoryType.DECISION: "Decisions made during conversations",
    MemoryType.INSIGHT: "Important insights about the user or their work",
    MemoryType.CONTEXT: "Context about projects, ongoing work",
    MemoryType.GOAL: "Goals, objectives, milestones",
    MemoryType.CHAT: "Conversation summaries for context",
    MemoryType.FEEDBACK: "User feedback, corrections, preferences",
    MemoryType.PERSONAL: "Personal information (hobbies, family, etc.)",
}
