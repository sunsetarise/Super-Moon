"""Bounded asynchronous qualification DAG with dependency blocking."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Mapping

from .contracts import ExecutionStatus, InvalidInput


@dataclass(frozen=True, slots=True)
class TrackTask:
    task_id: str
    dependencies: tuple[str, ...]
    action: Callable[[], Awaitable[Mapping[str, object]]]
    timeout_seconds: float = 3600.0
    retries: int = 0

    def __post_init__(self) -> None:
        if not self.task_id or self.timeout_seconds <= 0 or self.retries < 0:
            raise InvalidInput("invalid track task")


@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: str
    status: ExecutionStatus
    attempts: int
    payload: Mapping[str, object]
    message: str = ""


class QualificationOrchestrator:
    def __init__(self, max_concurrency: int = 4):
        if max_concurrency <= 0:
            raise InvalidInput("max_concurrency must be positive")
        self.max_concurrency = max_concurrency

    @staticmethod
    def _validate(tasks: Mapping[str, TrackTask]) -> None:
        if set(tasks) != {task.task_id for task in tasks.values()}:
            raise InvalidInput("task dictionary keys and task IDs differ")
        for task in tasks.values():
            missing = set(task.dependencies) - set(tasks)
            if missing:
                raise InvalidInput(f"task {task.task_id} has missing dependencies: {missing}")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise InvalidInput("qualification task graph contains a cycle")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency in tasks[task_id].dependencies:
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in tasks:
            visit(task_id)

    async def run(self, tasks: Mapping[str, TrackTask]) -> dict[str, TaskResult]:
        self._validate(tasks)
        semaphore = asyncio.Semaphore(self.max_concurrency)
        futures: dict[str, asyncio.Task[TaskResult]] = {}

        async def execute(task: TrackTask) -> TaskResult:
            dependencies = [await futures[item] for item in task.dependencies]
            if any(not row.status.successful for row in dependencies):
                return TaskResult(task.task_id, ExecutionStatus.BLOCKED, 0, {}, "dependency did not pass")
            last_error = ""
            for attempt in range(1, task.retries + 2):
                try:
                    async with semaphore:
                        payload = await asyncio.wait_for(task.action(), timeout=task.timeout_seconds)
                    return TaskResult(task.task_id, ExecutionStatus.PASS, attempt, dict(payload))
                except asyncio.TimeoutError:
                    last_error = "timeout"
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
            return TaskResult(task.task_id, ExecutionStatus.FAIL, task.retries + 1, {}, last_error)

        for task_id in self._topological(tasks):
            futures[task_id] = asyncio.create_task(execute(tasks[task_id]))
        return {task_id: await future for task_id, future in futures.items()}

    @staticmethod
    def _topological(tasks: Mapping[str, TrackTask]) -> tuple[str, ...]:
        remaining = set(tasks)
        completed: set[str] = set()
        order: list[str] = []
        while remaining:
            ready = sorted(task_id for task_id in remaining if set(tasks[task_id].dependencies) <= completed)
            if not ready:
                raise InvalidInput("qualification task graph contains a cycle")
            order.extend(ready)
            completed.update(ready)
            remaining.difference_update(ready)
        return tuple(order)

