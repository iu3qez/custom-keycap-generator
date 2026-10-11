"""SVG legends must not disturb the other legends on the same cap."""
import os
import tempfile

from _helpers import make_key

# A closed square and an open stroke, like a small Lucide icon (24u viewbox).
_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
<path d="M4 4 H20 V20 H4 Z" fill="none" stroke="black" stroke-width="2"/>
<path d="M8 12 H16" fill="none" stroke="black" stroke-width="2"/>
</svg>"""


def _svg_path():
    path = os.path.join(tempfile.mkdtemp(), "icon.svg")
    with open(path, "w") as f:
        f.write(_SVG)
    return path


# A closed path that crosses itself (figure eight), like Lucide "command".
_SVG_CROSSING = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
<path d="M4 4 L20 20 L20 4 L4 20 Z" fill="none" stroke="black" stroke-width="2"/>
</svg>"""


def _write(svg):
    path = os.path.join(tempfile.mkdtemp(), "icon.svg")
    with open(path, "w") as f:
        f.write(svg)
    return path


def test_self_crossing_closed_path_gives_valid_cap():
    # filling a self-crossing wire gives an invalid face; it must be stroked
    k = make_key(legends=[{"svg": _write(_SVG_CROSSING), "size": 3.2, "dx": -4, "dy": 4}])
    assert k.shape().is_valid
    assert k.legend_plug().is_valid


def test_svg_keeps_earlier_text_legends():
    # svg_legend_sketch runs inside the cutter's BuildSketch; build123d's
    # scale() defaults to Mode.REPLACE there, which used to wipe the text
    # legends added before the icon and leave a stray icon at the origin.
    k = make_key(legends=[
        {"text": "T", "size": 4.6, "dx": -4, "dy": 4},
        {"text": "6", "size": 2.5, "dx": 4, "dy": 4},
        {"svg": _svg_path(), "size": 3.2, "dx": -4, "dy": -4},
    ])
    solids = k._legend_cutter.solids()
    quads = {("T" if s.center().Y > 0 else "B") + ("L" if s.center().X < 0 else "R")
             for s in solids}
    assert quads == {"TL", "TR", "BL"}, quads
    assert not [s for s in solids
                if abs(s.center().X) < 1.5 and abs(s.center().Y) < 1.5]


if __name__ == "__main__":
    test_svg_keeps_earlier_text_legends(); print("OK svg keeps earlier text legends")
    test_self_crossing_closed_path_gives_valid_cap(); print("OK self-crossing closed path is stroked")
