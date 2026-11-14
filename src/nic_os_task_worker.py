"""Trusted in-process NIC task scheduler.

This first scheduler runs inside the owner API service process so owner-control
state and the task store remain in the trusted control plane. It exposes no
shell, browser, filesystem-write, publishing, trading, or deployment tools.
Task model calls are routed through advisor_reply and OwnerAuthorizedToolBroker.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable

from src.nic_os_owner_control_store import OwnerControlStore
from src.nic_os_task_runtime import TaskRuntimeStore

log = logging.getLogger(__name__)


def _model_task_executor(task: dict[str, Any], grant_id: str,
                         owner_store: OwnerControlStore,
                         task_store: TaskRuntimeStore) -> str:
    """Run one task through NIC's existing broker-gated, read-only chat runtime."""
    from src.nic_assistant_chat import advisor_reply

    def stopped() -> bool:
        if owner_store.status().get("emergency_stop", True):
            return True
        try:
            current = task_store.get_task(task["task_id"])
        except KeyError:
            return True
        return current["status"] != "running" or current.get("lease_id") != task.get("lease_id")

    return advisor_reply(
        task["goal"],
        client=None,
        max_tool_calls=3,
        owner_store=owner_store,
        autonomy_grant_id=grant_id,
        autonomy_task_id=task["task_id"],
        stop_check=stopped,
    )


class NICTaskWorker:
    """Claim only tasks covered by live owner grants; fence all completions by lease."""

    def __init__(
        self,
        task_store: TaskRuntimeStore,
        owner_store: OwnerControlStore,
        *,
        worker_id: str = "nic-trusted-runtime",
        executor: Callable[[dict[str, Any], str, OwnerControlStore, TaskRuntimeStore], str] | None = None,
        poll_seconds: float = 2.0,
        lease_seconds: int = 300,
    ):
        if not isinstance(poll_seconds, (int, float)) or not 0.25 <= poll_seconds <= 60:
            raise ValueError("poll_seconds_must_be_between_0.25_and_60")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 900:
            raise ValueError("lease_seconds_must_be_between_30_and_900")
        self.task_store = task_store
        self.owner_store = owner_store
        self.worker_id = worker_id
        self.executor = executor or _model_task_executor
        self.poll_seconds = float(poll_seconds)
        self.lease_seconds = lease_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def run_once(self) -> bool:
        """Run at most one explicitly authorized task. Return whether work was claimed."""
        grants = self.owner_store.active_task_grants()
        if not grants or self.owner_store.status().get("emergency_stop", True):
            return False
        task = self.task_store.claim_next(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
            eligible_task_ids=list(grants),
            owner_id=self.owner_store.owner_identity,
        )
        if task is None:
            return False
        task_id = task["task_id"]
        grant_id = grants.get(task_id)
        if not grant_id:
            self.task_store.transition(
                task_id, new_status="paused", actor=self.worker_id,
                lease_id=task["lease_id"], error="owner_grant_not_found",
            )
            return True

        heartbeat_stop = threading.Event()
        heartbeat_failed = threading.Event()

        def heartbeat() -> None:
            interval = max(1.0, min(60.0, self.lease_seconds / 3.0))
            while not heartbeat_stop.wait(interval):
                try:
                    self.task_store.renew_lease(
                        task_id, worker_id=self.worker_id,
                        lease_id=task["lease_id"], lease_seconds=self.lease_seconds,
                    )
                except Exception:
                    heartbeat_failed.set()
                    return

        heartbeat_thread = threading.Thread(
            target=heartbeat, name="nic-task-lease-heartbeat", daemon=True
        )
        heartbeat_thread.start()
        try:
            result = self.executor(task, grant_id, self.owner_store, self.task_store)
            current = self.task_store.get_task(task_id)
            # Owner pause/cancel revokes the lease; a stale worker may never commit.
            if current["status"] != "running" or current.get("lease_id") != task["lease_id"]:
                return True
            if heartbeat_failed.is_set():
                raise RuntimeError("worker_lease_renewal_failed")
            if not isinstance(result, str) or not result.strip():
                raise RuntimeError("task_executor_returned_empty_result")
            if not self.owner_store.task_grant_is_active(task_id=task_id, grant_id=grant_id):
                self.task_store.transition(
                    task_id, new_status="paused", actor=self.worker_id,
                    lease_id=task["lease_id"], error="owner_stop_or_grant_revoked",
                )
                return True
            self.task_store.transition(
                task_id, new_status="completed", actor=self.worker_id,
                lease_id=task["lease_id"], result={"summary": result[:18000]},
            )
        except Exception as exc:
            try:
                current = self.task_store.get_task(task_id)
                if current["status"] == "running" and current.get("lease_id") == task["lease_id"]:
                    self.task_store.transition(
                        task_id, new_status="failed", actor=self.worker_id,
                        lease_id=task["lease_id"],
                        error=(type(exc).__name__ + ": task execution failed")[:2000],
                    )
            except Exception:
                pass
            log.warning("NIC task %s failed (%s)", task_id, type(exc).__name__)
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=2.0)
        return True

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self.run_forever, name="nic-task-scheduler", daemon=True
        )
        self._thread.start()

    def stop(self, *, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:
                log.warning("NIC task scheduler cycle failed (%s)", type(exc).__name__)
            self._stop.wait(self.poll_seconds)


def start_configured_worker(task_store: TaskRuntimeStore | None,
                            owner_store: OwnerControlStore | None) -> NICTaskWorker | None:
    """Opt-in startup; disabled unless explicitly enabled by trusted service config."""
    enabled = os.getenv("NIC_TASK_WORKER_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return None
    if task_store is None or owner_store is None:
        raise RuntimeError("task_worker_requires_task_and_owner_control_stores")
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError("task_worker_requires_model_provider_configuration")
    worker = NICTaskWorker(
        task_store,
        owner_store,
        poll_seconds=float(os.getenv("NIC_TASK_WORKER_POLL_SECONDS", "2")),
        lease_seconds=int(os.getenv("NIC_TASK_WORKER_LEASE_SECONDS", "300")),
    )
    worker.start()
    return worker
