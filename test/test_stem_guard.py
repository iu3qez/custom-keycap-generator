from _helpers import make_key


def test_stem_guard_is_cylinder_at_stem():
    k = make_key(legends=[])
    bb = k.stem_guard().bounding_box()
    # cylinder radius = Cherry tube (stem.stem_rad) -> XY extent = 2*radius
    assert abs(bb.size.X - 2 * k.stem.stem_rad) < 0.05
    assert abs(bb.size.Y - 2 * k.stem.stem_rad) < 0.05
    # height = stem_depth, sitting on z=0
    assert abs(bb.size.Z - k.stem_depth) < 0.05
    assert abs(bb.min.Z - 0.0) < 0.05
    # centered on the stem axis
    assert abs(bb.center().X) < 0.05
    assert abs(bb.center().Y) < 0.05


def test_stem_guard_contains_the_cross():
    # must fully enclose the Cherry cross cavity: the + arms reach
    # +/- cross_height/2 in X and Y, over the full stem_depth.
    k = make_key(legends=[])
    bb = k.stem_guard().bounding_box()
    half = k.cross_height / 2.0
    assert bb.max.X >= half and bb.max.Y >= half
    assert bb.min.X <= -half and bb.min.Y <= -half
    assert bb.max.Z >= k.stem_depth - 0.01


def test_stem_guard_never_none():
    # every key has a stem, so a guard is always produced
    assert make_key(legends=[]).stem_guard().volume > 0
    assert make_key(legends=[{"text": "Q"}]).stem_guard().volume > 0


if __name__ == "__main__":
    test_stem_guard_is_cylinder_at_stem(); print("OK cylinder at stem")
    test_stem_guard_contains_the_cross(); print("OK contains the cross")
    test_stem_guard_never_none(); print("OK guard never none")
