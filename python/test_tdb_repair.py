"""Offline tests for tools/tdb_repair.py using a tiny synthetic TDB fragment.

No MatCalc/ODbL data is embedded here; the fragment only imitates the dialect
quirks (unsupported directives, semicolon head, malformed limit, missing '!',
blank in REF tag, MatCalc-only HMVA parameter, bibliography text).

Run from python/: python -B -m unittest test_tdb_repair
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))
import tdb_repair as tr  # noqa: E402

SYNTHETIC = """$ synthetic dialect fragment, not real data
ELEMENT A    BCC_A2   10.0 1000.0 20.0 !
ELEMENT B    BCC_A2   20.0 2000.0 30.0 !
ELEMENT VA   VACUUM   0.0 0.0 0.0 !
REFERENCE_ELEMENT A !
FUNCTION GA 273.00 -1000+2*T; 6000.00  N !
FUNCTION GB 273.00 -2000+3*T; 6000.00  N !
PHASE ALPHA % 1 1 !
CONSTITUENT ALPHA :A,B : !
ADD_COMPOSITION_SET ALPHA :A: !
PARAMETER G(ALPHA,A;0) 273.00 +GA#; 6000.00.00  N
REF:1 !
PARAMETER G(ALPHA,B;0) 273.00 +GB#; 6000.00  N
PARAMETER L(ALPHA,A,B;0) 273.00 +500+1.5*T; 6000.00  N
REF: two words !
PARAMETER HMVA(ALPHA,*;0)
 273.00 +170000; 6000.00  N
REF:151 !
PARAMETER G(PHB;A:B;0) 273.00 +GA#+GB#; 6000.00  N
REF:2 !
LIST_OF_REFERENCES
A0001  free text bibliography line that is not TDB syntax
"""

AMBIGUOUS = """ELEMENT A BCC_A2 10.0 1000.0 20.0 !
PARAMETER G(PHX,A:A;0) 273.00 273 +46000-23*T; 6000.00  N ; 6000.00  N
REF:1 !
"""


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class TdbRepairTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tdb-repair-test-"))
        self.src = self.tmp / "syn.tdb"
        self.src.write_text(SYNTHETIC, encoding="utf-8", newline="\n")
        self.dst = self.tmp / "out" / "syn_repaired.tdb"

    def test_repairs_are_reported_and_applied(self):
        before = sha(self.src)
        rep = tr.repair_file(self.src, self.dst, "synthetic test")
        out = self.dst.read_text(encoding="utf-8")
        counts = rep["ruleCounts"]
        self.assertEqual(counts["drop-directive"], 2)
        self.assertEqual(counts["drop-matcalc-parameter"], 1)
        self.assertEqual(counts["semicolon-to-comma"], 1)
        self.assertEqual(counts["fix-temperature-limit"], 1)
        self.assertEqual(counts["insert-missing-terminator"], 1)
        self.assertEqual(counts["ref-tag-blank"], 1)
        self.assertEqual(counts["comment-out-bibliography"], 1)
        self.assertIn("PARAMETER G(PHB,A:B;0)", out)
        self.assertNotIn("6000.00.00", out)
        self.assertIn("REF:two_words", out)
        self.assertTrue(out.startswith("$ ---"))
        self.assertIn("Open Database License", out)
        # every non-comment line left is syntactically what pycalphad expects
        for line in out.splitlines():
            if line.lstrip().startswith("$"):
                continue
            self.assertNotIn("REFERENCE_ELEMENT", line)
            self.assertNotIn("ADD_COMPOSITION_SET", line)
            self.assertNotIn("HMVA", line)
        self.assertEqual(sha(self.src), before, "original must stay untouched")

    def test_thermodynamic_parameters_unchanged(self):
        rep = tr.repair_file(self.src, self.dst, "synthetic test")
        self.assertEqual(rep["parametersRetained"], 4)
        a = tr._retained_params(SYNTHETIC)
        b = tr._retained_params(self.dst.read_text(encoding="utf-8"))
        self.assertEqual(a, b)
        out = self.dst.read_text(encoding="utf-8")
        for expr in ("+GA#; 6000.00  N", "+GB#; 6000.00  N", "+500+1.5*T; 6000.00  N",
                     "+GA#+GB#; 6000.00  N"):
            self.assertIn(expr, out)

    def test_strict_refuses_dropping_matcalc_parameters(self):
        with self.assertRaises(tr.RepairRefused):
            tr.repair_file(self.src, self.dst, "synthetic test", strict=True)
        self.assertFalse(self.dst.exists())

    def test_ambiguous_construct_refused_unless_allowed(self):
        amb = self.tmp / "amb.tdb"
        amb.write_text(AMBIGUOUS, encoding="utf-8", newline="\n")
        with self.assertRaises(tr.RepairRefused):
            tr.repair_file(amb, self.tmp / "amb_out.tdb", "synthetic test")
        rep = tr.repair_file(amb, self.tmp / "amb_out.tdb", "synthetic test", allow_ambiguous=True)
        self.assertEqual(rep["ruleCounts"]["ambiguous-stray-number"], 1)
        self.assertEqual(rep["ruleCounts"]["ambiguous-duplicate-range-tail"], 1)
        self.assertTrue(all(r.get("assumption") for r in rep["repairs"]
                            if r["rule"].startswith("ambiguous")))

    def test_refuses_to_overwrite_original_and_cli_report(self):
        with self.assertRaises(tr.RepairRefused):
            tr.repair_file(self.src, self.src, "synthetic test")
        report = self.tmp / "r.json"
        rc = tr.main([str(self.src), str(self.dst), "--report", str(report)])
        self.assertEqual(rc, 0)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(data["sourceSha256"], sha(self.src))

    def test_parameter_change_is_detected(self):
        # A tampered "repair" must be caught by the preservation check.
        orig = "PARAMETER G(PHB;A:B;0) 273.00 +GA#; 6000.00  N"
        self.assertNotEqual(tr.canon_param(orig), tr.canon_param(orig.replace("+GA#", "+GB#")))
        self.assertEqual(tr.canon_param(orig), tr.canon_param(orig.replace("(PHB;", "(PHB,")))

    def test_function_ref_tag_on_next_line_is_joined_and_normalised(self):
        src = self.tmp / "fn.tdb"
        src.write_text(
            "ELEMENT A BCC_A2 10.0 1000.0 20.0 !\n"
            "FUNCTION GX 273.00 -1000+2*T; 6000.00  N \n"
            "REF: 170 !\n"
            "FUNCTION GY 273.00 -2000+3*T; 6000.00  N\n"
            "REF:171 !\n"
            "FUNCTION GZ 273.00 -3000+4*T; 6000.00  N !\n",
            encoding="utf-8", newline="\n")
        dst = self.tmp / "fn_repaired.tdb"
        rep = tr.repair_file(src, dst, "synthetic test")
        out = dst.read_text(encoding="utf-8")
        self.assertIn("FUNCTION GX 273.00 -1000+2*T; 6000.00  N REF:170!", out)
        self.assertIn("FUNCTION GY 273.00 -2000+3*T; 6000.00  N REF:171!", out)
        self.assertIn("FUNCTION GZ 273.00 -3000+4*T; 6000.00  N !", out)
        self.assertEqual(rep["ruleCounts"].get("function-ref-join"), 2)
        # the expression and limits are untouched
        self.assertIn("-1000+2*T; 6000.00", out)

    def test_pycalphad_loads_repaired_fragment_when_available(self):
        try:
            from pycalphad import Database
        except Exception:
            self.skipTest("pycalphad not installed in this interpreter")
        tr.repair_file(self.src, self.dst, "synthetic test")
        db = Database(str(self.dst))
        self.assertIn("ALPHA", db.phases)


if __name__ == "__main__":
    unittest.main()
