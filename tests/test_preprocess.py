import cv2
import numpy as np
import pytest

from alpr.preprocess import crop_box, deskew, estimate_skew, find_split_row, is_two_line, split_lines
from alpr.synth import render_plate


@pytest.fixture
def rng():
    return np.random.default_rng(0)


def test_crop_box_pads_and_clips():
    img = np.zeros((100, 200, 3), np.uint8)
    crop = crop_box(img, (0, 0, 100, 50), pad=0.1)
    assert crop.shape[:2] == (55, 110)  # clipped at top/left, padded at bottom/right


def test_is_two_line(rng):
    assert not is_two_line(render_plate(["51G-123.45"], rng))
    assert is_two_line(render_plate(["59-X1", "123.45"], rng))


def test_split_row_falls_between_lines(rng):
    plate = render_plate(["59-X1", "123.45"], rng)
    h = plate.shape[0]
    y = find_split_row(plate)
    # text baselines are at 42% and 86% of the height; the gap is roughly 45%-55%
    assert 0.42 * h <= y <= 0.6 * h
    top, bottom = split_lines(plate)
    assert top.shape[0] + bottom.shape[0] == h


def test_split_row_light_text_on_dark_plate(rng):
    plate = 255 - render_plate(["59-X1", "123.45"], rng)
    y = find_split_row(plate)
    assert 0.42 * plate.shape[0] <= y <= 0.6 * plate.shape[0]


@pytest.mark.parametrize("angle", [-8.0, -4.0, 4.0, 8.0])
def test_deskew_levels_rotated_plate(rng, angle):
    plate = render_plate(["51G-123.45"], rng)
    h, w = plate.shape[:2]
    canvas = cv2.copyMakeBorder(plate, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(230, 230, 230))
    ch, cw = canvas.shape[:2]
    m = cv2.getRotationMatrix2D((cw / 2, ch / 2), angle, 1.0)
    rotated = cv2.warpAffine(canvas, m, (cw, ch), borderValue=(230, 230, 230))

    before = abs(estimate_skew(rotated))
    after = abs(estimate_skew(deskew(rotated)))
    assert before > 2.0
    assert after < before / 2


def test_deskew_leaves_level_plate(rng):
    plate = render_plate(["51G-123.45"], rng)
    assert np.array_equal(deskew(plate), plate)
