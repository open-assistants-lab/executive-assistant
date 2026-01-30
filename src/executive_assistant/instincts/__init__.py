"""Instincts package for behavioral pattern learning."""

from executive_assistant.instincts.injector import get_instinct_injector
from executive_assistant.instincts.observer import get_instinct_observer
from executive_assistant.instincts.evolver import get_instinct_evolver

__all__ = ["get_instinct_injector", "get_instinct_observer", "get_instinct_evolver"]
