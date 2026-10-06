import pytest

from alpr.metrics import char_accuracy, levenshtein, plate_accuracy


@pytest.mark.parametrize(
    "a, b, d", [("", "", 0), ("abc", "abc", 0), ("abc", "abd", 1), ("", "abc", 3), ("kitten", "sitting", 3)]
)
def test_levenshtein(a, b, d):
    assert levenshtein(a, b) == d
    assert levenshtein(b, a) == d


def test_plate_and_char_accuracy_use_normalized_text():
    preds = ["51G-123.45", "59X112346", ""]
    gts = ["51G12345", "59-X1 123.45", "30A12345"]
    assert plate_accuracy(preds, gts) == pytest.approx(1 / 3)
    # errors: 0 + 1 + 8 over 8 + 9 + 8 chars
    assert char_accuracy(preds, gts) == pytest.approx(1 - 9 / 25)
