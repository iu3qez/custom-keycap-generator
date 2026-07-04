from _helpers import make_key

def test_no_legends_is_none():
    k = make_key(legends=[])
    assert k._legend_cutter is None
    assert k.legend_plug() is None
    assert k.shape().volume > 0

def test_recess_and_plug_invariant():
    plain = make_key(legends=[])
    legended = make_key(legends=[{"text": "Q"}])

    base_v = plain.shape().volume
    body_v = legended.shape().volume
    plug = legended.legend_plug()

    assert plug is not None
    plug_v = plug.volume
    assert plug_v > 0
    assert body_v < base_v                       # recess was carved
    # body + plug reconstruct the smooth cap (single-intersection invariant)
    assert abs((body_v + plug_v) - base_v) < 0.5   # mm^3

def test_plug_is_thin_shard_near_top():
    k = make_key(legends=[{"text": "Q"}])
    bb = k.legend_plug().bounding_box()
    assert bb.size.Z < 1.5      # ~0.8mm deep plug
    assert bb.max.Z > 5.0       # sits at the top of a ~6mm cap

def test_glyph_key_builds():
    # Adwaita glyph must render real geometry (not tofu / empty)
    k = make_key(legends=[{"text": "⇥"}])
    assert k.legend_plug().volume > 0

if __name__ == "__main__":
    test_no_legends_is_none(); print("OK no-legend is None")
    test_recess_and_plug_invariant(); print("OK recess + plug invariant")
    test_plug_is_thin_shard_near_top(); print("OK plug thin shard near top")
    test_glyph_key_builds(); print("OK glyph key builds")
