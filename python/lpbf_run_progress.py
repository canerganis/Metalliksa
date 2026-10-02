"""Opt-in, bounded CPU work accounting; snapshots are not valid field outputs."""
from contextvars import ContextVar
from functools import wraps
from inspect import signature
import math

_CURRENT = ContextVar("lpbf_cpu_run_progress", default=None)


def current_progress():
    return _CURRENT.get()


def validate_cpu_progress(progress, p):
    if progress is None:
        return
    if not isinstance(progress, CpuRunProgress):
        raise ValueError("run_progress must be a CpuRunProgress instance")
    if progress._started:
        raise ValueError("CpuRunProgress instances are single-use")
    if (p["mode"] != "standard" or p["backend"] != "reference" or p["study"] != "none"
            or p.get("thermalModelId") == "layered-plate-enthalpy-v1"):
        raise ValueError("Run progress supports standard reference CPU runs without a study only")


class CpuRunProgress:
    def __init__(self, observer=None, *, maximum_source_evaluations=None,
                 maximum_source_cell_steps=None):
        if observer is not None and not callable(observer):
            raise ValueError("Progress observer must be callable")
        for value in (maximum_source_evaluations, maximum_source_cell_steps):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Source work budgets must be nonnegative integers")
        self.observer = observer
        self.maximum_source_evaluations = maximum_source_evaluations
        self.maximum_source_cell_steps = maximum_source_cell_steps
        self._started = False
        self._observer_failed = False
        self._state = {"schemaVersion": 1, "scope": "cpu-reference", "stage": "running",
                       "acceptedSteps": 0, "lastAcceptedTime_s": 0.,
                       "lastAcceptedSchedulerTime_s": 0., "lastAcceptedDt_s": None,
                       "attemptedSourceEvaluations": 0, "sourceEvaluationRetries": 0,
                       "attemptedSourceCellSteps": 0, "sourceEvaluationFailures": 0,
                       "cells": None}

    def snapshot(self):
        return self._state.copy()

    def _emit(self):
        if self.observer is not None:
            try:
                self.observer(self.snapshot())
            except Exception:
                self._observer_failed = True
                raise

    def begin(self):
        if self._started:
            raise ValueError("CpuRunProgress instances are single-use")
        self._started = True
        self._emit()

    def set_cells(self, cells):
        if type(cells) is not int or cells <= 0:
            raise ValueError("CPU progress cell count must be positive")
        self._state["cells"] = cells

    def before_source_evaluation(self, retry_index):
        cells = self._state["cells"]
        if cells is None:
            raise RuntimeError("CPU source work accounting requires the resolved cell count")
        evaluations = self._state["attemptedSourceEvaluations"]+1
        work = self._state["attemptedSourceCellSteps"]+cells
        if self.maximum_source_evaluations is not None and evaluations > self.maximum_source_evaluations:
            raise RuntimeError("CPU source-evaluation budget would be exceeded")
        if self.maximum_source_cell_steps is not None and work > self.maximum_source_cell_steps:
            raise RuntimeError("CPU source cell-step budget would be exceeded")
        self._state["attemptedSourceEvaluations"] = evaluations
        self._state["attemptedSourceCellSteps"] = work
        self._state["sourceEvaluationRetries"] += int(retry_index > 0)

    def source_evaluation_failed(self):
        self._state["sourceEvaluationFailures"] += 1

    def accept(self, dt, clock, scheduler_time):
        if not (math.isfinite(dt) and dt > 0 and math.isfinite(clock)
                and clock > self._state["lastAcceptedTime_s"] and math.isfinite(scheduler_time)):
            raise RuntimeError("CPU accepted-progress clock is invalid")
        self._state.update(acceptedSteps=self._state["acceptedSteps"]+1,
                           lastAcceptedTime_s=float(clock), lastAcceptedDt_s=float(dt),
                           lastAcceptedSchedulerTime_s=float(scheduler_time))
        self._emit()

    def complete(self):
        self._state["stage"] = "completed"
        self._emit()

    def fail(self, exception):
        self._state.update(stage="failed", failureType=type(exception).__name__, reason=str(exception))
        # A failed observer must never replace the original solver/callback failure.
        if not self._observer_failed:
            try:
                self._emit()
            except Exception as callback_error:
                self._state["failureObserverError"] = f"{type(callback_error).__name__}: {callback_error}"
        exception.progress = self.snapshot()


def track_cpu_progress(function):
    call_signature = signature(function)

    @wraps(function)
    def tracked(*args, **kwargs):
        bound = call_signature.bind_partial(*args, **kwargs)
        progress = bound.arguments.get("run_progress")
        if progress is None:
            return function(*args, **kwargs)
        validate_cpu_progress(progress, bound.arguments["p"])
        if current_progress() is not None:
            raise ValueError("CPU run-progress scopes cannot be nested")
        token = _CURRENT.set(progress)
        try:
            progress.begin()
            result = function(*args, **kwargs)
            progress.complete()
            return result
        except Exception as exc:
            progress.fail(exc)
            raise
        finally:
            _CURRENT.reset(token)
    return tracked
