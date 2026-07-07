"""Unit checks for the Vial parser and keycode->legend resolver.

Pure Python: no geometry, no network (icons are resolved with fetch=False, so
this stays fast and offline). Run: uv run python test/test_vial.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vial import (
    parse_board, parse_keymap, keycodes_for, resolve_keycode,
    quadrant_legends, QuadrantSpec, Legend,
)

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "fixtures", "planck_board.json")
KEYMAP = os.path.join(HERE, "fixtures", "planck_keymap.vil")


# --- board parsing --------------------------------------------------------- #
keys = parse_board(BOARD)
assert len(keys) == 48, f"expected 48 keys, got {len(keys)}"
by_pos = {(k.row, k.col): k for k in keys}
assert (0, 0) in by_pos and (3, 11) in by_pos
# KLE cursor: col advances x by width, rows advance y.
assert by_pos[(0, 0)].x == 0.0 and by_pos[(0, 0)].y == 0.0
assert by_pos[(0, 5)].x == 5.0, by_pos[(0, 5)].x
assert by_pos[(2, 0)].y == 2.0
assert all(k.w == 1.0 for k in keys)
print("OK board parses to 48 unit keys at expected grid positions")


# --- keymap parsing -------------------------------------------------------- #
layout = parse_keymap(KEYMAP)
assert len(layout) == 4, f"expected 4 layers, got {len(layout)}"
q = by_pos[(0, 1)]
kcs = keycodes_for(layout, q, 4)
assert kcs == ["KC_Q", "KC_1", "KC_EXLM", "KC_BRIU"], kcs
print("OK keymap gives per-layer keycodes for a matrix cell")


# --- keycode resolution ---------------------------------------------------- #
assert resolve_keycode("KC_Q") == Legend("text", "Q")
assert resolve_keycode("KC_5") == Legend("text", "5")
assert resolve_keycode("KC_LSFT") == Legend("icon", "arrow-big-up")
assert resolve_keycode("KC_ENT") == Legend("icon", "corner-down-left")
assert resolve_keycode("KC_SCLN") == Legend("text", ";")
assert resolve_keycode("KC_MINS") == Legend("text", "-")
assert resolve_keycode("KC_EXLM") == Legend("text", "!")   # shifted symbol
assert resolve_keycode("KC_LPRN") == Legend("text", "(")
assert resolve_keycode("KC_ESC") == Legend("text", "Esc")
assert resolve_keycode("KC_F7") == Legend("text", "F7")
assert resolve_keycode("KC_TRNS") is None
assert resolve_keycode("KC_NO") is None
assert resolve_keycode("_______") is None
assert resolve_keycode("KC_SPC") is None           # blank spacebar -> no legend
assert resolve_keycode("MO(1)") == Legend("text", "L1")
assert resolve_keycode("LT(2, KC_A)") == Legend("text", "A")   # tap key shown
assert resolve_keycode("LSFT(KC_B)") == Legend("text", "B")
assert resolve_keycode("KC_LEFT") == Legend("icon", "arrow-left")
print("OK keycodes resolve to text / icon / None as specified")


# --- quadrant legends (offline: no icon fetch) ----------------------------- #
spec = QuadrantSpec()
key_h = 18.0
legs = quadrant_legends(["KC_Q", "KC_1", "KC_AT", "KC_TRNS"],
                        key_h, key_h, spec, fetch=False)
# layer 0 (Q text, large, top-left) + layer 1 (1 text, small, top-right).
# layer 2 KC_AT -> "@" is not a mapped symbol -> text fallback; layer 3 TRNS skipped.
assert len(legs) == 3, legs
main = legs[0]
assert main["text"] == "Q" and main["size"] == spec.main_text
assert main["dx"] < 0 and main["dy"] > 0, "layer 0 must be top-left"
top_right = legs[1]
assert top_right["text"] == "1" and top_right["size"] == spec.sub_text
assert top_right["dx"] > 0 and top_right["dy"] > 0, "layer 1 must be top-right"
print("OK quadrant placement: layer0 large top-left, subs clockwise")

# icon legends carry the Lucide name when not fetched.
legs2 = quadrant_legends(["KC_LSFT"], key_h, key_h, spec, fetch=False)
assert legs2[0].get("icon") == "arrow-big-up" and legs2[0]["size"] == spec.main_icon
assert legs2[0]["dx"] < 0 and legs2[0]["dy"] > 0
print("OK icon legend records Lucide name + main size in top-left")

print("\nAll Vial parser checks passed.")
