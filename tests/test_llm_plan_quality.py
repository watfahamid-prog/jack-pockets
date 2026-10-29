import unittest

from llm import _concrete_keyword_terms, _normalize_plan


def make_plan(keywords):
    beats = []
    for index in range(8):
        narration = (
            f"Beat {index} explains one clear evidence question. "
            + " ".join(f"observation{index}_{word}" for word in range(180))
            + "."
        )
        beats.append({
            "title": f"Evidence chapter {index}",
            "narration": narration,
            "keywords": list(keywords),
            "source_urls": [],
        })
    return {"title": "Test documentary", "beats": beats}


class LLMPlanKeywordQualityTests(unittest.TestCase):
    def test_concrete_keyword_terms_exclude_visual_mood_and_production_words(self):
        self.assertEqual(
            _concrete_keyword_terms(["cinematic footage sequence", "bizarre future story"]),
            set(),
        )
        self.assertEqual(
            _concrete_keyword_terms(["AS 7007 router incident", "NANOG route leak"]),
            {"router", "nanog", "route", "leak"},
        )

    def test_rejects_plans_with_two_keyword_entries_but_no_concrete_subjects(self):
        with self.assertRaisesRegex(ValueError, "concrete subject terms"):
            _normalize_plan(make_plan(["cinematic footage sequence", "bizarre future story"]), "test")

    def test_malformed_keyword_shape_fails_with_validation_error(self):
        plan = make_plan(["AS 7007 router incident", "NANOG route leak"])
        plan["beats"][0]["keywords"] = 42
        with self.assertRaisesRegex(ValueError, "concrete subject terms"):
            _normalize_plan(plan, "test")

    def test_non_list_citation_metadata_is_not_treated_as_approved_urls(self):
        plan = make_plan(["AS 7007 router incident", "NANOG route leak"])
        plan["beats"][0]["source_urls"] = {"https://example.org/looks-like-a-source": True}
        normalized = _normalize_plan(plan, "test")
        self.assertEqual(normalized["beats"][0]["source_urls"], [])

    def test_accepts_plans_with_concrete_searchable_subject_terms(self):
        normalized = _normalize_plan(
            make_plan(["AS 7007 router incident", "NANOG route leak"]),
            "test",
        )
        self.assertEqual(len(normalized["beats"]), 8)


if __name__ == "__main__":
    unittest.main()
