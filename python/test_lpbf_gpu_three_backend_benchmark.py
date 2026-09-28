import unittest
from unittest.mock import patch

import run_lpbf_gpu_three_backend_benchmark as bench


class HarnessProtocolTests(unittest.TestCase):
    @staticmethod
    def sessions():
        sessions=[]
        for i, order in enumerate(bench.ORDERS):
            samples={k:[float(i+1),float(i+2),float(i+3),float(i+4),float(i+5)] for k in bench.BACKENDS}
            measurements=[]
            for round_no in range(1,bench.ROUNDS+1):
                for label in order:
                    measurements.append({"round":round_no,"backend":label,
                        "solveAndFinalCaptureWall_s":samples[label][round_no-1]})
            sessions.append({"session":i+1,"order":list(order),"identity":{"hash":"same"},
                "samples":samples,"measurements":measurements})
        return sessions

    def test_rotated_orders_and_bounds(self):
        self.assertEqual(bench.ORDERS, (("cpu", "torch", "warp"),
            ("torch", "warp", "cpu"), ("warp", "cpu", "torch")))
        self.assertEqual(bench.ROUNDS, 5)
        with self.assertRaises(ValueError): bench.run(None, 0)
        with self.assertRaises(ValueError): bench.run(None, bench.MAX_TIMEOUT + 1)
        with self.assertRaises(ValueError): bench._positive(float("nan"))

    def test_schema_and_medians(self):
        sessions=self.sessions()
        report=bench._aggregate(sessions)
        self.assertEqual(report["schemaVersion"],1)
        self.assertEqual(report["roundsPerBackendPerSession"],5)
        self.assertEqual(report["totalSamplesPerBackend"],15)
        self.assertEqual(report["summary"]["cpu"]["median_s"],4.0)
        self.assertEqual(report["summary"]["cpu"]["sampleCount"],15)
        self.assertIn("kernel stages",report["scope"]["excludedTiming"])
        self.assertEqual(report["scope"]["unmeasuredStages"]["kernelStages"],"not-measured")
        self.assertIn("parityPreflight",report["timingStage"])
        self.assertIn("firstCudaCall",report["timingStage"])
        self.assertIn("not separated",report["sessionWallDefinition"])
        self.assertEqual(report["scope"]["geometryCellQuantization_um"],40)
        self.assertTrue(report["scope"]["finalStateFieldGate"])
        self.assertIn("archive/persistence",report["scope"]["excludedTiming"])

    def test_warmup_timer_includes_synchronization(self):
        events=[]
        with patch.object(bench.time,"perf_counter",side_effect=[10.0,12.5]):
            elapsed=bench._warmup_call(lambda: events.append("call"),
                                       lambda: events.append("sync"))
        self.assertEqual(events,["call","sync"])
        self.assertEqual(elapsed,2.5)

    def test_refuses_wrong_order_or_identity(self):
        rows=self.sessions()
        bad=[dict(x) for x in rows]; bad[1]["order"]=list(bench.ORDERS[0])
        with self.assertRaises(ValueError): bench._aggregate(bad)
        bad=[dict(x) for x in rows]; bad[2]["identity"]={"hash":"changed"}
        with self.assertRaises(ValueError): bench._aggregate(bad)
        bad=[dict(x) for x in rows]; bad[0]["samples"]={**bad[0]["samples"],"warp":[1,2]}
        with self.assertRaises(ValueError): bench._aggregate(bad)

    def test_aggregate_requires_session_samples_and_measurement_order(self):
        rows=self.sessions(); rows[0]["session"]=2
        with self.assertRaises(ValueError): bench._aggregate(rows)
        rows=self.sessions(); rows[1]["samples"]["cpu"]=[1.0,2.0]
        with self.assertRaises(ValueError): bench._aggregate(rows)
        rows=self.sessions(); rows[0]["measurements"][0]["backend"]="warp"
        with self.assertRaises(ValueError): bench._aggregate(rows)
        rows=self.sessions(); rows[2]["samples"]["torch"][0]=99.0
        with self.assertRaises(ValueError): bench._aggregate(rows)

    def test_nan_metrics_fail_closed(self):
        self.assertFalse(bench._within_relative(float("nan"),1.0,.01))
        self.assertFalse(bench._within_relative(1.0,float("nan"),.01))
        self.assertFalse(bench._within_absolute(float("nan"),0.0,40.0))

    def test_refuses_cuda_unavailable(self):
        class Cuda:
            @staticmethod
            def is_available(): return False
        class Torch: cuda=Cuda()
        with patch.dict("sys.modules", {"torch":Torch()}):
            with self.assertRaisesRegex(RuntimeError,"CUDA unavailable"):
                bench._worker(0)


if __name__ == "__main__": unittest.main()
