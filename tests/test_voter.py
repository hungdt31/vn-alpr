from alpr.tracking.voter import TrackVoter


def test_confirms_after_min_hits_with_agreement():
    v = TrackVoter(min_hits=3, min_agreement=0.6, max_age=5)
    assert v.update(1, "51G12345", "51G-123.45", 0.9, True, 0) is None
    assert v.update(1, "51G12845", "51G-128.45", 0.4, True, 1) is None  # one misread
    ev = v.update(1, "51G12345", "51G-123.45", 0.9, True, 2)
    assert ev is not None
    assert ev.text == "51G12345" and ev.track_id == 1 and ev.hits == 3
    assert v.is_emitted(1)
    # never emitted twice
    assert v.update(1, "51G12345", "51G-123.45", 0.9, True, 3) is None


def test_invalid_reads_do_not_count():
    v = TrackVoter(min_hits=2)
    v.update(1, "51G1", "51G1", 0.9, False, 0)
    assert v.update(1, "51G12345", "51G-123.45", 0.9, True, 1) is None
    assert v.update(1, "51G12345", "51G-123.45", 0.9, True, 2) is not None


def test_low_agreement_waits_then_flushes_best_guess():
    v = TrackVoter(min_hits=2, min_agreement=0.8, max_age=3)
    v.update(7, "AAA", "AAA", 0.5, True, 0)
    assert v.update(7, "BBB", "BBB", 0.6, True, 1) is None  # 55% < 80%
    assert v.flush(3) == []  # not stale yet
    events = v.flush(5)
    assert len(events) == 1 and events[0].text == "BBB"
    assert v.best(7) is None  # dropped


def test_flush_force_and_reset():
    v = TrackVoter(min_hits=1, min_agreement=0.0)
    assert v.update(1, "X", "X", 1.0, True, 0) is not None
    v.update(2, "Y", "Y", 1.0, False, 0)  # never valid -> nothing to emit
    assert v.flush(0, force=True) == []
    assert v.best(1) is None
