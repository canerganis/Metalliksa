"""Failure-log filtering tests for the LPBF worker's execution boundary."""
import json
import unittest

import lpbf_worker


def _frame(progress, message="working", **extra):
    value = {"progress": progress, "message": message, **extra}
    return json.dumps(value, allow_nan=True, separators=(",", ":"))


class ExecutionFailureMessageTests(unittest.TestCase):
    def failure_message(self, final_log, returncode=17):
        helper = getattr(lpbf_worker, "_execution_failure_message", None)
        self.assertTrue(callable(helper), "worker should expose its failure-log formatter")
        return helper(final_log, returncode)

    def test_only_exact_valid_progress_frames_are_removed(self):
        frames = [
            _frame(0),
            _frame(0.25, "source integration"),
            _frame(1, "finished"),
        ]
        retained = ["solver warning: retry", "ValueError: thermal audit failed"]
        original = "\n".join([frames[0], retained[0], frames[1], retained[1], frames[2]])
        original_snapshot = original

        result = self.failure_message(original)

        self.assertIn(retained[0], result)
        self.assertIn(retained[1], result)
        for line in frames:
            self.assertNotIn(line, result)
        self.assertEqual(result, "\n".join(retained) + "\n")
        self.assertEqual(original, original_snapshot, "input log remains unchanged")

    def test_malformed_and_non_frame_json_lines_are_preserved(self):
        lines = [
            "{not json",
            _frame(float("nan")),
            _frame(float("inf")),
            _frame("0.5"),
            _frame(True),
            _frame(-0.01),
            _frame(1.01),
            _frame(0.5, message=7),
            _frame(0.5, extra="not an exact two-key frame"),
            '{"progress":0.5,"progress":0.75,"message":"duplicate key"}',
            '{"progress":' + str(10 ** 300) + ',"message":"huge integer"}',
            json.dumps({"message": "missing progress"}),
            json.dumps({"progress": 0.5}),
            "ordinary diagnostic text",
        ]

        result = self.failure_message("\n".join(lines))

        for line in lines:
            self.assertIn(line, result)

    def test_deep_json_is_retained_without_recursion_error(self):
        deeply_nested = "[" * 1500 + "0" + "]" * 1500
        self.assertLess(len(deeply_nested), 4000)

        result = self.failure_message(deeply_nested + "\nordinary error")

        self.assertEqual(result, deeply_nested + "\nordinary error")

    def test_traceback_error_and_last_valid_cpu_summary_are_retained(self):
        diagnostic = [
            "Traceback (most recent call last):",
            "  File 'lpbf_simulation.py', line 12, in run",
            "ValueError: injected failure",
            "Last valid CPU state: 4 accepted steps at 0.000004 s. Source work: 8 source evaluations, 2 retries, 64 source cell-evaluations (excludes conduction and other solver work). No completed result.",
        ]
        log = "\n".join([_frame(0.5), *diagnostic, _frame(0.75)])

        result = self.failure_message(log)

        for line in diagnostic:
            self.assertIn(line, result)
        self.assertNotIn(_frame(0.5), result)
        self.assertNotIn(_frame(0.75), result)

    def test_tail_limit_is_applied_after_valid_frames_are_filtered(self):
        frame = _frame(0.5, "X" * 6000)
        log = "A" * 4500 + "\n" + frame + "\n" + "Z" * 100
        expected = ("A" * 4500 + "\n" + "Z" * 100)[-4000:]

        result = self.failure_message(log)

        self.assertEqual(result, expected)
        self.assertLessEqual(len(result), 4000)
        self.assertNotIn("X", result)

    def test_valid_frames_only_fall_back_to_solver_exit_code(self):
        log = "\n".join([_frame(0.1), _frame(1, "complete")])

        self.assertEqual(self.failure_message(log, returncode=23), "Solver exit 23")

    def test_crlf_diagnostics_blank_lines_and_indentation_are_preserved(self):
        frame = _frame(0.5, "working")
        diagnostic = "\r\n  warning\r\n    traceback detail\r\n"
        log = frame + "\r\n" + diagnostic + _frame(0.75, "more work") + "\r\n"

        self.assertEqual(self.failure_message(log), diagnostic)

    def test_whitespace_only_log_falls_back_to_solver_exit_code(self):
        self.assertEqual(self.failure_message(" \r\n\t\n  ", returncode=9), "Solver exit 9")


if __name__ == "__main__":
    unittest.main()
