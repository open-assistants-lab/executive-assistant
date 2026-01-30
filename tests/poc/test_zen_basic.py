#!/usr/bin/env python3
"""Test zen-engine basic functionality."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import zen

# Try a minimal decision graph from GoRules docs
minimal_decision = {
    "name": "test_decision",
    "nodes": [
        {
            "id": "true-node",
            "type": "decision",
            "expression": "input.value === true",
            "outputs": {
                "result": "yes"
            }
        },
        {
            "id": "false-node",
            "type": "decision",
            "expression": "input.value === false",
            "outputs": {
                "result": "no"
            }
        }
    ]
}

try:
    engine = zen.ZenEngine()
    decision = engine.create_decision(minimal_decision)

    result = decision.evaluate({"input": {"value": True}})
    print(f"✅ SUCCESS: {result}")

    result2 = decision.evaluate({"input": {"value": False}})
    print(f"✅ SUCCESS: {result2}")

    print("\n✅ zen-engine basic functionality works!")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
