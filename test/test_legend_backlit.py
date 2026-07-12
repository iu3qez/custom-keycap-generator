"""Backlit (through-hole + diffuser) legend mode checks."""
from _helpers import make_key

# A quadrant legend, like the real Vial sets: offset from center, clear of the
# stem clearance so it lands over the transparent diffuser.
QUAD = [{"text": "Q", "size": 4.6, "dx": -3.96, "dy": 4.32}]


def test_backlit_off_by_default():
    k = make_key(legends=[{"text": "Q"}])
    assert k.legend_through is False
    assert k._diffuser is None


def test_through_cut_reaches_the_ceiling():
    # In backlit mode the recess is a through-hole: the plug spans from the
    # inner ceiling (diffuser bottom) all the way to the cap top, not a ~0.8mm
    # shard.
    flush = make_key(legends=QUAD)
    lit = make_key(legends=QUAD, legend_through=True)

    flush_z = flush.legend_plug().bounding_box().size.Z
    lit_z = lit.legend_plug().bounding_box().size.Z
    assert flush_z < 1.5                      # blind recess shard
    assert lit_z > flush_z + 0.5              # through-column + diffuser is deep
    # diffuser bottom sits on the inner ceiling (stem_depth + inner_rad)
    assert abs(lit.legend_plug().bounding_box().min.Z - lit._top_inner_z) < 1e-6


def test_backlit_mass_is_conserved():
    plain = make_key(legends=[])
    lit = make_key(legends=QUAD, legend_through=True)
    body = lit.shape()
    plug = lit.legend_plug()
    # body + plug reconstruct the full cap exactly (nothing lost/added)
    assert abs((body.volume + plug.volume) - plain.shape().volume) < 0.5


def test_backlit_body_stays_single_solid():
    # The diffuser must not sever the stem post from the cap: the opaque body
    # keeps a pillar around the stem, so it stays one connected solid.
    lit = make_key(legends=QUAD, legend_through=True)
    assert len(lit.shape().solids()) == 1


def test_diffuser_sits_below_the_top():
    lit = make_key(legends=QUAD, legend_through=True)
    dbb = lit._diffuser.bounding_box()
    assert abs(dbb.min.Z - lit._top_inner_z) < 1e-6
    assert abs(dbb.size.Z - lit.diffuser_depth) < 1e-6


if __name__ == "__main__":
    test_backlit_off_by_default(); print("OK backlit off by default")
    test_through_cut_reaches_the_ceiling(); print("OK through-cut reaches ceiling")
    test_backlit_mass_is_conserved(); print("OK backlit mass conserved")
    test_backlit_body_stays_single_solid(); print("OK body stays single solid")
    test_diffuser_sits_below_the_top(); print("OK diffuser below top")
