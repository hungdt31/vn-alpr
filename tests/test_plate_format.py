import pytest

from alpr.postprocess.plate_format import is_valid_plate, normalize, parse_plate


def test_normalize_strips_separators_and_d_stroke():
    assert normalize("51g-123.45") == "51G12345"
    assert normalize("29-MĐ1 123.45") == "29MD112345"
    assert normalize(" 30a - 999 . 99 ") == "30A99999"


@pytest.mark.parametrize(
    "lines, text, display",
    [
        (["51G-123.45"], "51G12345", "51G-123.45"),
        (["30LD-123.45"], "30LD12345", "30LD-123.45"),
        (["51G-1234"], "51G1234", "51G-1234"),
        (["59-X1", "123.45"], "59X112345", "59-X1 123.45"),
        (["51G", "123.45"], "51G12345", "51G 123.45"),
        (["29-MĐ1", "123.45"], "29MD112345", "29-MD1 123.45"),
    ],
)
def test_parse_valid_plates(lines, text, display):
    p = parse_plate(lines)
    assert p.valid
    assert p.text == text
    assert p.display == display
    assert p.n_fixes == 0


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("S1G12345", "51G12345"),  # S in a digit position -> 5
        ("516123A5", "51G12345"),  # 6 in the series position -> G, A in number -> 4
        ("51GI2B45", "51G12845"),  # I -> 1, B -> 8
        ("5IG-O23.45", "51G02345"),
    ],
)
def test_position_based_fixes(raw, expected):
    p = parse_plate(raw)
    assert p.valid
    assert p.text == expected
    assert p.n_fixes > 0


def test_fix_disabled_rejects_confusions():
    assert not parse_plate("S1G12345", fix=False).valid
    assert parse_plate("51G12345", fix=False).valid


def test_two_line_uses_first_line_length():
    # "59X1" as line 1 must be read as motorbike series X1, not car series X + 6-digit number
    p = parse_plate(["59X1", "12345"])
    assert p.display == "59-X1 123.45"
    # an O read in the series digit position of line 1 becomes 0
    p = parse_plate(["59-XO", "12345"])
    assert p.valid and p.text == "59X012345"


def test_two_line_falls_back_when_split_is_off():
    p = parse_plate(["59X11", "2345"])  # split one character late
    assert p.valid
    assert p.text == "59X112345"


@pytest.mark.parametrize("raw", ["", "ABC", "51G123", "51G1234567", "5", "####"])
def test_invalid(raw):
    assert not parse_plate(raw).valid


def test_is_valid_plate():
    assert is_valid_plate("51G-123.45")
    assert is_valid_plate("59-X1 123.45")
    assert not is_valid_plate("hello")
