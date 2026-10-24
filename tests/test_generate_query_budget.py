import unittest

from generate import _asset_query_limit


class AssetQueryBudgetTests(unittest.TestCase):
    def test_default_two_assets_allows_third_fallback_query(self):
        self.assertEqual(_asset_query_limit(2), 3)

    def test_small_asset_budget_still_allows_two_queries(self):
        self.assertEqual(_asset_query_limit(1), 2)

    def test_query_count_is_bounded_for_larger_asset_budgets(self):
        self.assertEqual(_asset_query_limit(3), 3)
        self.assertEqual(_asset_query_limit(4), 3)


if __name__ == "__main__":
    unittest.main()
