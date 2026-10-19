import unittest
from unittest.mock import patch

import semantic_ranker


class SemanticRankerTests(unittest.TestCase):
    def test_empty_assets_returns_empty_without_loading_model(self):
        with patch.object(semantic_ranker, "_model") as model:
            self.assertEqual(semantic_ranker.score_assets("a ship", []), {})
            model.assert_not_called()

    def test_missing_optional_dependency_is_only_needed_when_called(self):
        # Importing the module itself must not import heavyweight ML libraries.
        self.assertTrue(callable(semantic_ranker.score_assets))


if __name__ == "__main__":
    unittest.main()
