import unittest
from unittest.mock import patch
import generate

class GenerateOrchestrationTests(unittest.TestCase):
    def test_asset_query_limit_is_bounded(self):
        self.assertEqual(generate._asset_query_limit(1), 2)
        self.assertEqual(generate._asset_query_limit(2), 3)
        self.assertEqual(generate._asset_query_limit(4), 3)

    def test_invalid_asset_count_fails_before_generation(self):
        with patch("sys.argv", ["generate.py", "--topic", "Test", "--assets-per-beat", "9"]):
            with self.assertRaises(SystemExit) as error:
                generate.main()
        self.assertEqual(error.exception.code, 2)

if __name__ == "__main__":
    unittest.main()
