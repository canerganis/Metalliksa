"""require_git_revision: skip locally, fail in CI when an old-blob revision is missing."""

import unittest

from phase6a_test_support import require_git_revision


def _run(cls):
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(cls).run(result)
    return result


def _case():
    class Case(unittest.TestCase):
        def test_x(self):
            pass
    return Case


class RequireGitRevisionTest(unittest.TestCase):
    def test_available_runs_normally(self):
        result = _run(require_git_revision(True, "r", env={"CI": "true"})(_case()))
        self.assertEqual((result.testsRun, len(result.errors), len(result.skipped)), (1, 0, 0))

    def test_unavailable_skips_outside_ci(self):
        for env in ({}, {"CI": ""}):
            result = _run(require_git_revision(False, "rev missing", env=env)(_case()))
            self.assertEqual(len(result.skipped), 1, env)
            self.assertTrue(result.wasSuccessful())

    def test_unavailable_fails_in_ci(self):
        result = _run(require_git_revision(False, "rev missing", env={"CI": "true"})(_case()))
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.skipped), 0)
        self.assertIn("fetch-depth: 0", result.errors[0][1])


if __name__ == "__main__":
    unittest.main()
