import unittest

from llm import SYSTEM, _research_prompt


class ClaimEvidencePromptTests(unittest.TestCase):
    def test_system_prompt_requires_direct_support_for_factual_claims(self):
        self.assertIn(
            "do not claim a source supports a point unless its title/snippet/abstract actually relates to that point",
            SYSTEM,
        )
        self.assertIn(
            "Never invent quotes, statistics, dates, or events",
            SYSTEM,
        )
        self.assertIn(
            "If the evidence is uncertain or sources disagree, say so in the narration",
            SYSTEM,
        )

    def test_research_prompt_limits_citations_to_supplied_exact_urls(self):
        prompt = _research_prompt(
            "Example topic",
            [
                {
                    "title": "Official report",
                    "url": "https://example.org/report",
                    "content": "A specific finding in the report.",
                }
            ],
        )
        self.assertIn("use only exact URLs listed above", prompt)
        self.assertIn("never fabricate citations", prompt)
        self.assertIn("https://example.org/report", prompt)
        self.assertIn("A specific finding in the report.", prompt)

    def test_research_prompt_does_not_inject_sources_without_urls(self):
        prompt = _research_prompt(
            "Example topic",
            [
                {"title": "No URL", "content": "This must not be treated as a citable source."},
                {"title": "Has URL", "url": "https://example.org/valid", "content": "Valid source."},
            ],
        )
        self.assertNotIn("This must not be treated as a citable source.", prompt)
        self.assertIn("https://example.org/valid", prompt)


if __name__ == "__main__":
    unittest.main()
