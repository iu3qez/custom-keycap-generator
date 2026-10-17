"""generate_vial.py --emit-layout --layout-only: an editable layout YAML that
main.py can build (offline: icons stay as Lucide names, nothing is fetched)."""
import os
import subprocess
import sys
import tempfile

import yaml

import _helpers  # noqa: F401  (puts the repo root on sys.path)

from orca3mf import board_to_plate
from vial import resolve_icon_legends

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_layout_only():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "luma40.yaml")
        subprocess.run(
            [sys.executable, "generate_vial.py", "g20", "configs/keymaps/luma40.vil",
             "--emit-layout", out, "--layout-only", "-o", tmp],
            cwd=ROOT, check=True, capture_output=True)
        assert not [f for f in os.listdir(tmp) if f.endswith((".stl", ".3mf"))], \
            "--layout-only must not build caps"
        keys = yaml.safe_load(open(out))["keys"]
    assert len(keys) == 47
    for name, k in keys.items():
        assert {"base", "width", "pos", "legends"} <= k.keys(), name
        for leg in k["legends"]:
            assert "svg" not in leg, f"{name}: icons are written by name"
            assert ("text" in leg) != ("icon" in leg), name
    assert any("icon" in leg for k in keys.values() for leg in k["legends"])
    # 2u spacebar (interior -1 gap in the matrix) keeps its width and position
    wide = [k for k in keys.values() if k["width"] == 2.0]
    assert len(wide) == 1 and wide[0]["pos"] == [5.0, 3.0]
    print("OK layout-only YAML: 47 keys, pos/width, icons by name, no caps built")


def test_layout_only_needs_path():
    r = subprocess.run(
        [sys.executable, "generate_vial.py", "g20", "test/fixtures/planck_keymap.vil",
         "--layout-only"], cwd=ROOT, capture_output=True)
    assert r.returncode != 0
    print("OK --layout-only without --emit-layout is rejected")


def test_text_legends_pass_through():
    legs = [{"text": "Q", "size": 5.5}]
    assert resolve_icon_legends(legs) == legs
    print("OK resolve_icon_legends leaves text legends alone")


def test_board_to_plate():
    keys = [("a", (9.5, 9.5), {}), ("b", (114.0, 66.5), {})]
    placed = dict((n, xy) for n, xy, _ in board_to_plate(keys))
    assert placed["a"] == (19.5, 67.0) and placed["b"] == (124.0, 10.0)
    print("OK board_to_plate flips y and adds the 10 mm margin")


if __name__ == "__main__":
    test_layout_only()
    test_layout_only_needs_path()
    test_text_legends_pass_through()
    test_board_to_plate()
