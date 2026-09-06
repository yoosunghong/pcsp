import json
from pathlib import Path
import tempfile
import unittest

from run_evaluation import matrix
from summarize_evaluation import summarize


class EvaluationTests(unittest.TestCase):
    def test_counterbalanced_pairing(self):
        cases = list(matrix([0], [17, 18, 19], [16]))
        self.assertEqual([v for _, v, _, _ in cases], [0, 1, 2, 1, 2, 0, 2, 0, 1])
        self.assertEqual(len(set(cases)), 9)
        with self.assertRaises(ValueError):
            list(matrix([1], [17], [1024]))

    def test_summary_excludes_smokes_and_separates_context(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = []
            for index, (width, cpu, complete, functional) in enumerate([
                (1280, 10, True, False), (1280, 20, True, False),
                (1920, 30, True, False), (1280, 99, True, True),
                (1280, 99, False, False),
            ]):
                row = dict(axis=0, variant=0, npc_count=16, map="Map", world_type="Game",
                           width=width, height=720, vsync=0, fps_cap=0, seed=index,
                           complete=complete, invalid_reason="", fps=60, cpu_pct=cpu,
                           p95_frame_ms=20, action_entropy_bits=1, comparison_scope="fixture")
                path = Path(directory) / f"{index}.json"
                path.write_text(json.dumps(row), encoding="utf-8")
                manifest.append(dict(passed=True, functional_only=functional, results=[str(path)]))
            result = summarize(manifest)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["n"], 2)
            self.assertEqual(result[0]["cpu_pct"]["mean"], 15)
            self.assertEqual(result[1]["width"], 1920)


if __name__ == "__main__":
    unittest.main()
