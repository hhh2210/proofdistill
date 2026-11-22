import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import lexer_metrics as lm


class LexerMetricsTests(unittest.TestCase):
    def test_strips_nested_block_and_line_comments(self):
        src = "/- outer /- inner sorry -/ still comment -/\n-- sorry\ntheorem foo : True := by trivial\n"
        res = lm.analyze_source(src)
        self.assertEqual(res["forbidden_hits"], [])
        self.assertEqual(res["code_lines"], 1)
        self.assertGreater(res["norm_tokens"], 5)

    def test_catches_forbidden_keywords_in_code(self):
        for bad in ["theorem a : False := by sorry", "axiom cheat : False", "theorem b : 1 = 1 := by native_decide"]:
            res = lm.analyze_source(bad)
            self.assertTrue(res["forbidden_hits"], f"failed to catch: {bad}")

    def test_one_liner_cannot_game_norm_tokens(self):
        multiline = "theorem a (x : Nat) : x = x := by\n  have h := rfl\n  exact h\n"
        oneliner = "theorem a (x : Nat) : x = x := by have h := rfl; exact h\n"
        r1 = lm.analyze_source(multiline)
        r2 = lm.analyze_source(oneliner)
        self.assertEqual(r1["code_lines"], 3)
        self.assertEqual(r2["code_lines"], 1)
        # One-liner actually has MORE or equal tokens because of ';'
        self.assertGreaterEqual(r2["norm_tokens"], r1["norm_tokens"])


if __name__ == "__main__":
    unittest.main()
