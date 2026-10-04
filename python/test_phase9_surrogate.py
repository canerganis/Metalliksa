import unittest
from pathlib import Path

try:
    from phase9_surrogate import generate_synthetic_data, train_surrogate, predict_surrogate
except ImportError as _exc:
    _PHASE9_MISSING = str(_exc)
else:
    _PHASE9_MISSING = None

if _PHASE9_MISSING is not None:
    @unittest.skip("phase9 surrogate dependencies unavailable (scikit-learn/joblib): " + _PHASE9_MISSING)
    class Phase9SurrogateUnavailable(unittest.TestCase):
        def test_phase9_surrogate_unavailable(self):
            pass
else:
    class Phase9Surrogate(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            # pytest ran the training test first; unittest sorts alphabetically, so train once up front.
            train_surrogate("IN718", 20)

        def test_phase9_surrogate_training(self):
            # Train a very small model just for test
            path_str = train_surrogate("IN718", 20)
            self.assertTrue(Path(path_str).exists())

        def test_phase9_surrogate_prediction_in_distribution(self):
            # Assume model is trained from the previous test or manually
            # P=300, V=1000, T0=100 should be well within (100,500) and (400,2000) and (25,200)
            res = predict_surrogate("IN718", 300, 1000, 100)
            self.assertIs(res["surrogate_used"], True)
            self.assertGreater(res["width_um"], 0)
            self.assertGreater(res["depth_um"], 0)
            self.assertIs(res["error_budget"]["is_out_of_distribution"], False)
            self.assertGreater(res["error_budget"]["confidence_pct"], 80.0) # High confidence for in-distribution

        def test_phase9_surrogate_prediction_out_of_distribution(self):
            # Extreme parameters
            res = predict_surrogate("IN718", 1000, 50, 500)
            self.assertIs(res["error_budget"]["is_out_of_distribution"], True)
            self.assertEqual(res["error_budget"]["confidence_pct"], 0.0) # Confidence goes to 0 outside bounds


if __name__ == "__main__":
    unittest.main()
