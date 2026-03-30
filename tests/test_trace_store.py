"""Tests for TraceStore."""

import pytest

from agendum.models import ExecutionTrace, TaskCompletionStatus
from agendum.store.trace_store import TraceStore


@pytest.fixture
def trace_store(tmp_path):
    root = tmp_path / ".agendum"
    root.mkdir()
    return TraceStore(root)


class TestTraceStore:
    def test_write_and_list(self, trace_store):
        trace = ExecutionTrace(
            task_id="task-001",
            project="myapp",
            agent_id="claude",
            completion_status=TaskCompletionStatus.DONE,
            duration_seconds=120.0,
            task_type="dev",
        )
        path = trace_store.write_trace(trace)
        assert path.exists()

        traces = trace_store.list_traces("myapp")
        assert len(traces) == 1
        assert traces[0].task_id == "task-001"
        assert traces[0].completion_status == TaskCompletionStatus.DONE

    def test_filter_by_plan_id(self, trace_store):
        trace_store.write_trace(
            ExecutionTrace(
                task_id="t1",
                project="myapp",
                agent_id="a",
                plan_id="plan-001",
            )
        )
        trace_store.write_trace(
            ExecutionTrace(
                task_id="t2",
                project="myapp",
                agent_id="a",
                plan_id="plan-002",
            )
        )
        traces = trace_store.list_traces("myapp", plan_id="plan-001")
        assert len(traces) == 1
        assert traces[0].task_id == "t1"

    def test_filter_by_task_id(self, trace_store):
        trace_store.write_trace(
            ExecutionTrace(
                task_id="t1",
                project="myapp",
                agent_id="a",
            )
        )
        trace_store.write_trace(
            ExecutionTrace(
                task_id="t2",
                project="myapp",
                agent_id="a",
            )
        )
        traces = trace_store.list_traces("myapp", task_id="t2")
        assert len(traces) == 1

    def test_list_nonexistent_project(self, trace_store):
        assert trace_store.list_traces("nonexistent") == []
