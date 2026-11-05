import unittest

from scripts.update_tracker import RatingFetchError, extract_current_rating


class ExtractCurrentRatingTests(unittest.TestCase):
    def test_reads_current_rating_not_highest_or_lowest(self):
        payload = {
            "statsInfo": {"stats": {"rating": 1724}},
            "highest": {"rating": 2400},
            "lowest": {"rating": 900},
            "puzzleRush": {"score": 40},
        }
        self.assertEqual(extract_current_rating(payload), 1724)

    def test_accepts_numeric_string(self):
        self.assertEqual(extract_current_rating({"statsInfo": {"stats": {"rating": "1501"}}}), 1501)

    def test_rejects_payload_without_current_rating(self):
        with self.assertRaises(RatingFetchError):
            extract_current_rating({"statsInfo": {"stats": {"highest": {"rating": 2500}}}})

    def test_rejects_null_rating(self):
        with self.assertRaises(RatingFetchError):
            extract_current_rating({"statsInfo": {"stats": {"rating": None}}})

    def test_rejects_implausible_rating(self):
        with self.assertRaises(RatingFetchError):
            extract_current_rating({"statsInfo": {"stats": {"rating": 999999}}})

    def test_rejects_fractional_rating_instead_of_truncating_it(self):
        with self.assertRaises(RatingFetchError):
            extract_current_rating({"statsInfo": {"stats": {"rating": 1501.7}}})


if __name__ == "__main__":
    unittest.main()
