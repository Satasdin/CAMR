"""Checks on the marking rules. Run:  python test_score.py"""
import unittest

import score
from scoring import includes_all, is_correct, last_number, last_number_is, normalise, sign_test


class MustInclude(unittest.TestCase):
    def test_every_group_needs_one(self):
        groups = [["silver thrip", "thrips"], ["Wanjiru", "Oduya"]]
        self.assertTrue(includes_all("It is the Silver  Thrip; chosen by wanjiru.", groups))
        self.assertTrue(includes_all("Thrips. Ms Oduya picked it.", groups))
        self.assertFalse(includes_all("It is the silver thrip.", groups))
        self.assertFalse(includes_all("Wanjiru Oduya chose it.", groups))

    def test_case_and_whitespace(self):
        self.assertTrue(includes_all("the  LAKE\n blue glaze", [["Lake Blue"]]))

    def test_thousands_separators(self):
        self.assertTrue(includes_all("It harvested 1,250 kg.", [["1250"]]))
        self.assertTrue(includes_all("It harvested 1250 kg.", [["1,250"]]))
        self.assertTrue(includes_all("about 12,000,000 litres", [["12000000"]]))
        self.assertEqual(normalise("in 2019, 300 plants"), "in 2019, 300 plants")
        self.assertEqual(normalise("beds 1,2,3"), "beds 1,2,3")

    def test_empty_groups_and_answers(self):
        self.assertFalse(includes_all("anything", []))
        self.assertFalse(includes_all("", [["x"]]))
        self.assertFalse(is_correct({"type": "single", "must_include": [["x"]]}, None))

    def test_reasoning_printed_by_the_model_is_ignored(self):
        self.assertFalse(includes_all("<think>maybe 62</think>I don't know.", [["62"]]))


class LastNumber(unittest.TestCase):
    def test_last_number(self):
        self.assertEqual(last_number("3 boxes of 4 make 12."), 12)
        self.assertEqual(last_number("She earns $102,000 in total."), 102000)
        self.assertEqual(last_number("**Answer: 18**"), 18)
        self.assertEqual(last_number("so 10 - 12 = -2"), -2)
        self.assertEqual(last_number("between 10-12"), 12)
        self.assertEqual(last_number("It is 2.50"), 2.5)
        self.assertIsNone(last_number("I don't know."))

    def test_equal_numerically(self):
        self.assertTrue(last_number_is("The total is 18.0", "18"))
        self.assertTrue(last_number_is("#### 1,000", "1000"))
        self.assertFalse(last_number_is("18 eggs at 2 dollars", "18"))
        self.assertFalse(last_number_is("no number", "18"))

    def test_file_references_are_not_the_answer(self):
        self.assertTrue(last_number_is("The answer is 42.\nThis is stated in Garden/kiln.md:3.", "42"))
        self.assertTrue(last_number_is("42 (notes/a.md:10-12)", "42"))

    def test_task(self):
        task = {"type": "reasoning", "answer": "102000", "must_include": []}
        self.assertTrue(is_correct(task, "120 x 850 = 102,000"))
        self.assertFalse(is_correct(task, "120 x 850 = 102,500"))


class SignTest(unittest.TestCase):
    def test_known_values(self):
        self.assertAlmostEqual(sign_test(8, 2), 0.109375)      # 2 * (1 + 10 + 45) / 1024
        self.assertAlmostEqual(sign_test(2, 8), 0.109375)
        self.assertAlmostEqual(sign_test(10, 0), 2 / 1024)
        self.assertAlmostEqual(sign_test(5, 5), 1.0)
        self.assertAlmostEqual(sign_test(15, 3), 2 * 988 / 262144)     # 1 + 18 + 153 + 816 = 988
        self.assertEqual(sign_test(0, 0), 1.0)


class Summary(unittest.TestCase):
    def rows(self, marks, subject="s", kind="single", paths=None):
        return {"t%d" % i: {"id": "t%d" % i, "subject": subject, "type": kind, "correct": bool(m),
                            "seconds": 1.0 + i, "prompt_tokens": 100 * (i + 1),
                            "excerpt_paths": paths or [], "evidence": ["a.md", "b.md"]}
                for i, m in enumerate(marks)}

    def test_gap_closed(self):
        results = {"local_alone": self.rows([1, 0, 0, 0]), "local_engine": self.rows([1, 1, 1, 0]),
                   "cloud_alone": self.rows([1, 1, 1, 1])}
        gap = score.gap_closed(results, "local_engine")
        self.assertAlmostEqual(gap["all"]["gap_closed"], (0.75 - 0.25) / (1.0 - 0.25))
        self.assertEqual(gap["all"]["n"], 4)

    def test_gap_not_defined(self):
        results = {"local_alone": self.rows([1, 1]), "local_engine": self.rows([1, 1]),
                   "cloud_alone": self.rows([1, 0])}
        self.assertIsNone(score.gap_closed(results, "local_engine")["all"]["gap_closed"])
        self.assertIn("not defined", score.gap_text(score.gap_closed(results, "local_engine")["all"]))

    def test_pairs(self):
        results = {"local_alone": self.rows([0, 0, 1, 1]), "local_engine": self.rows([1, 1, 1, 0])}
        test = score.paired(results, "local_engine", "local_alone")
        self.assertEqual((test["a_only"], test["b_only"]), (2, 1))
        self.assertAlmostEqual(test["p"], 1.0)

    def test_evidence_recall(self):
        full = self.rows([1], paths=["./a.md", "b.md", "c.md"])
        part = self.rows([1], paths=["a.md"])
        self.assertEqual(score.evidence_recall(full)["all"]["recall"], 1.0)
        self.assertEqual(score.evidence_recall(part)["all"]["recall"], 0.0)
        self.assertEqual(score.evidence_recall(part)["all"]["any"], 1.0)

    def test_accuracy_table(self):
        table = score.accuracy(self.rows([1, 0, 1]))
        cell = table[("s", "single")]
        self.assertEqual((cell["n"], cell["correct"]), (3, 2))
        self.assertEqual(cell["median_seconds"], 2.0)
        self.assertEqual(cell["median_prompt_tokens"], 200)


if __name__ == "__main__":
    unittest.main()
