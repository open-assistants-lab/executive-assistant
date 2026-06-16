from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TestResult:
    name: str
    passed: bool
    duration_ms: int
    error: str | None = None
    tool_calls: int = 0
    tokens: int = 0
    response_preview: str = ""


@dataclass
class SuiteResult:
    category: str
    total: int
    passed: int
    results: list[TestResult]
    duration_ms: int


@dataclass
class SmokeReport:
    timestamp: str
    suites: list[SuiteResult]
    total_tests: int
    total_passed: int
    total_duration_ms: int
    model: str

    @property
    def total_failed(self) -> int:
        return self.total_tests - self.total_passed

    @property
    def pass_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.total_passed / self.total_tests) * 100.0
