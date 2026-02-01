"""Performance benchmarking for Phase 4 instincts system features.

Measures actual performance impact to make data-driven sync vs async decisions.
"""

import json
import time
from datetime import datetime, timezone, timedelta

import pytest

from executive_assistant.storage.instinct_storage import InstinctStorage
from executive_assistant.instincts.injector import get_instinct_injector
from executive_assistant.instincts.calibrator import get_confidence_calibrator


class TestPerformanceBenchmark:
    """Performance benchmark suite for Phase 4 features."""

    def setup_method(self):
        """Set up test fixtures."""
        self.storage = InstinctStorage()
        self.injector = get_instinct_injector()
        self.calibrator = get_confidence_calibrator()
        self.test_thread = "benchmark_thread"

    def teardown_method(self):
        """Clean up test data."""
        # Clean up benchmark thread data
        import shutil
        from pathlib import Path

        thread_dir = Path(f"data/instincts/{self.test_thread}")
        if thread_dir.exists():
            shutil.rmtree(thread_dir)

    def _create_test_instincts(self, count: int) -> list[str]:
        """Create specified number of test instincts.

        Args:
            count: Number of instincts to create

        Returns:
            List of instinct IDs
        """
        instinct_ids = []

        domains = [
            "communication",
            "workflow",
            "tool_selection",
            "format",
            "verification",
            "timing",
        ]

        for i in range(count):
            domain = domains[i % len(domains)]
            instinct_id = self.storage.create_instinct(
                trigger=f"test trigger {i}",
                action=f"test action {i}",
                domain=domain,
                confidence=0.5 + (i % 5) * 0.1,  # Varying confidence
                thread_id=self.test_thread,
            )
            instinct_ids.append(instinct_id)

        return instinct_ids

    def test_benchmark_build_instincts_context_10(self):
        """Benchmark build_instincts_context() with 10 instincts."""
        self._create_test_instincts(10)

        start = time.perf_counter()
        result = self.injector.build_instincts_context(
            thread_id=self.test_thread,
            user_message="test message for context",
        )
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000

        # Should be very fast with 10 instincts
        assert elapsed_ms < 50, f"Too slow: {elapsed_ms:.2f}ms for 10 instincts"
        assert result  # Should return some content

        print(f"\n✅ 10 instincts: {elapsed_ms:.2f}ms")

    def test_benchmark_build_instincts_context_50(self):
        """Benchmark build_instincts_context() with 50 instincts."""
        self._create_test_instincts(50)

        start = time.perf_counter()
        result = self.injector.build_instincts_context(
            thread_id=self.test_thread,
            user_message="test message for context",
        )
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000

        # Should be reasonably fast with 50 instincts
        assert elapsed_ms < 200, f"Too slow: {elapsed_ms:.2f}ms for 50 instincts"
        assert result  # Should return some content

        print(f"\n✅ 50 instincts: {elapsed_ms:.2f}ms")

    def test_benchmark_build_instincts_context_100(self):
        """Benchmark build_instincts_context() with 100 instincts."""
        self._create_test_instincts(100)

        start = time.perf_counter()
        result = self.injector.build_instincts_context(
            thread_id=self.test_thread,
            user_message="test message for context",
        )
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000

        # Should complete in reasonable time even with 100 instincts
        assert elapsed_ms < 500, f"Too slow: {elapsed_ms:.2f}ms for 100 instincts"
        assert result  # Should return some content

        print(f"\n✅ 100 instincts: {elapsed_ms:.2f}ms")

    def test_benchmark_find_similar_instincts(self):
        """Benchmark cross-instinct pattern recognition."""
        self._create_test_instincts(50)

        start = time.perf_counter()
        similar = self.storage.find_similar_instincts(
            thread_id=self.test_thread,
            similarity_threshold=0.5,
        )
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000

        # O(n²) but n=50 should be fast
        assert elapsed_ms < 100, f"Too slow: {elapsed_ms:.2f}ms for 50 instincts"

        print(f"\n✅ find_similar_instincts (50): {elapsed_ms:.2f}ms, {len(similar)} clusters")

    def test_benchmark_merge_similar_instincts(self):
        """Benchmark merging similar instincts."""
        # Create some duplicate instincts
        self.storage.create_instinct(
            trigger="be concise",
            action="keep responses brief",
            domain="communication",
            confidence=0.7,
            thread_id=self.test_thread,
        )
        self.storage.create_instinct(
            trigger="be concise",
            action="keep responses short",
            domain="communication",
            confidence=0.6,
            thread_id=self.test_thread,
        )

        start = time.perf_counter()
        result = self.storage.merge_similar_instincts(
            thread_id=self.test_thread,
            similarity_threshold=0.6,
        )
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000

        assert elapsed_ms < 100, f"Too slow: {elapsed_ms:.2f}ms"
        assert result["instincts_merged"] > 0

        print(f"\n✅ merge_similar_instincts: {elapsed_ms:.2f}ms, merged {result['instincts_merged']}")

    def test_benchmark_confidence_calibration(self):
        """Benchmark confidence calibration system."""
        # Record some predictions
        for i in range(100):
            self.calibrator.record_prediction(
                predicted_confidence=0.5 + (i % 5) * 0.1,
                actual_outcome=i % 2 == 0,  # Alternate True/False
                instinct_id=f"instinct_{i % 10}",
                thread_id=self.test_thread,
            )

        # Calibrate (should trigger after 100 records)
        start = time.perf_counter()
        self.calibrator._calibrate()
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000

        # Calibration should be fast even with 100 records
        assert elapsed_ms < 50, f"Too slow: {elapsed_ms:.2f}ms for 100 records"

        print(f"\n✅ confidence calibration (100 records): {elapsed_ms:.2f}ms")

    def test_benchmark_adaptive_injection(self):
        """Benchmark adaptive injection limits."""
        self._create_test_instincts(50)

        # Test adaptive mode (max_per_domain=None)
        start = time.perf_counter()
        result = self.injector.build_instincts_context(
            thread_id=self.test_thread,
            max_per_domain=None,  # Adaptive mode
        )
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000

        # Adaptive mode adds minimal overhead
        assert elapsed_ms < 200, f"Too slow: {elapsed_ms:.2f}ms for adaptive mode"

        print(f"\n✅ adaptive injection (50 instincts): {elapsed_ms:.2f}ms")

    def test_benchmark_export_import(self):
        """Benchmark export/import functionality."""
        self._create_test_instincts(50)

        # Benchmark export
        start = time.perf_counter()
        json_data = self.storage.export_instincts(
            thread_id=self.test_thread,
            min_confidence=0.0,
        )
        end = time.perf_counter()
        export_ms = (end - start) * 1000

        # Benchmark import
        start = time.perf_counter()
        result = self.storage.import_instincts(
            json_data=json_data,
            thread_id=f"{self.test_thread}_imported",
            merge_strategy="merge",
        )
        end = time.perf_counter()
        import_ms = (end - start) * 1000

        # Both should be fast
        assert export_ms < 50, f"Export too slow: {export_ms:.2f}ms"
        assert import_ms < 200, f"Import too slow: {import_ms:.2f}ms"

        print(f"\n✅ export (50 instincts): {export_ms:.2f}ms")
        print(f"✅ import (50 instincts): {import_ms:.2f}ms")

    def test_benchmark_temporal_decay_batch(self):
        """Benchmark temporal decay calculation."""
        self._create_test_instincts(50)

        # Make some instincts old
        instincts = self.storage.list_instincts(thread_id=self.test_thread)
        for instinct in instincts[:25]:
            instinct["created_at"] = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            self.storage._update_snapshot(instinct, self.test_thread)

        start = time.perf_counter()
        for instinct in instincts:
            self.storage.adjust_confidence_for_decay(instinct["id"], self.test_thread)
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000

        # Decay calculation should be fast
        assert elapsed_ms < 100, f"Too slow: {elapsed_ms:.2f}ms for 50 instincts"

        print(f"\n✅ temporal decay (50 instincts): {elapsed_ms:.2f}ms")

    def test_benchmark_full_pipeline(self):
        """Benchmark full instincts pipeline with all Phase 4 features."""
        # Create test data
        self._create_test_instincts(50)

        # Simulate full pipeline
        total_start = time.perf_counter()

        # 1. Load and build context (with metadata adjustments)
        start = time.perf_counter()
        context = self.injector.build_instincts_context(
            thread_id=self.test_thread,
            user_message="test message",
            max_per_domain=None,  # Adaptive mode
        )
        build_time = (time.perf_counter() - start) * 1000

        # 2. Find similar instincts
        start = time.perf_counter()
        similar = self.storage.find_similar_instincts(thread_id=self.test_thread)
        similar_time = (time.perf_counter() - start) * 1000

        # 3. Calibrate confidence
        for i in range(50):
            self.calibrator.record_prediction(
                predicted_confidence=0.7,
                actual_outcome=True,
                instinct_id=f"instinct_{i}",
                thread_id=self.test_thread,
            )
        start = time.perf_counter()
        self.calibrator._calibrate()
        calibrate_time = (time.perf_counter() - start) * 1000

        # 4. Export
        start = time.perf_counter()
        json_data = self.storage.export_instincts(thread_id=self.test_thread)
        export_time = (time.perf_counter() - start) * 1000

        total_elapsed = (time.perf_counter() - total_start) * 1000

        # Full pipeline should be fast
        assert total_elapsed < 1000, f"Full pipeline too slow: {total_elapsed:.2f}ms"

        print(f"\n✅ Full Pipeline Breakdown (50 instincts):")
        print(f"  - Build context: {build_time:.2f}ms")
        print(f"  - Find similar: {similar_time:.2f}ms")
        print(f"  - Calibrate: {calibrate_time:.2f}ms")
        print(f"  - Export: {export_time:.2f}ms")
        print(f"  - **TOTAL**: {total_elapsed:.2f}ms")

    def test_sync_vs_async_recommendation(self):
        """Provide data-driven recommendation for sync vs async.

        This test measures total overhead and makes a recommendation.
        """
        # Test with realistic instinct counts
        instinct_counts = [10, 50, 100]

        results = {}

        for count in instinct_counts:
            # Clean up previous test data
            self._create_test_instincts(count)

            # Measure build_instincts_context time
            iterations = 10
            times = []

            for _ in range(iterations):
                start = time.perf_counter()
                _ = self.injector.build_instincts_context(
                    thread_id=self.test_thread,
                    user_message="test message",
                    max_per_domain=None,  # Adaptive mode
                )
                end = time.perf_counter()
                times.append((end - start) * 1000)

            avg_time = sum(times) / len(times)
            max_time = max(times)
            results[count] = {
                "avg_ms": avg_time,
                "max_ms": max_time,
            }

        # Print results
        print("\n" + "="*60)
        print("PERFORMANCE BENCHMARK RESULTS")
        print("="*60)

        for count, metrics in results.items():
            print(f"\n{count} instincts:")
            print(f"  Average: {metrics['avg_ms']:.2f}ms")
            print(f"  Max:     {metrics['max_ms']:.2f}ms")

        # Make recommendation
        print("\n" + "="*60)
        print("RECOMMENDATION")
        print("="*60)

        # If worst case (100 instincts) is under 100ms, sync is fine
        if results[100]["max_ms"] < 100:
            print("\n✅ **SYNC approach is RECOMMENDED**")
            print("\nReasoning:")
            print("- Even with 100 instincts, overhead is <100ms")
            print("- This is <1% of typical LLM response time (5-10s)")
            print("- Async complexity outweighs benefits")
            print("- User experience impact is negligible")

            print("\nWhen to consider ASYNC:")
            print("- If instinct counts grow beyond 500")
            print("- If users report noticeable delays")
            print("- If adding more expensive features")

        else:
            print("\n⚠️ **ASYNC approach may be warranted**")
            print(f"\nReasoning:")
            print(f"- Overhead with 100 instincts: {results[100]['max_ms']:.2f}ms")
            print("- This approaches noticeable threshold")
            print("\nRecommendation:")
            print("- Implement async for expensive operations")
            print("- Keep sync for fast operations (<50ms)")

        print("\n" + "="*60)

        # Assertion to ensure baseline performance
        assert results[100]["avg_ms"] < 500, "Performance degradation detected"

    def test_memory_overhead(self):
        """Estimate memory overhead of instincts system."""
        import sys

        self._create_test_instincts(50)

        # Get instincts and estimate memory
        instincts = self.storage.list_instincts(thread_id=self.test_thread)

        # Rough estimate using sys.getsizeof
        total_size = 0
        for instinct in instincts:
            total_size += sys.getsizeof(instinct)
            for key, value in instinct.items():
                total_size += sys.getsizeof(key)
                total_size += sys.getsizeof(value)

        size_kb = total_size / 1024

        print(f"\n✅ Memory overhead (50 instincts): ~{size_kb:.2f} KB")

        # Should be minimal
        assert size_kb < 100, f"Memory overhead too high: {size_kb:.2f} KB"
