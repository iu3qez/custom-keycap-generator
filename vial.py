"""
Vial -> keycap legends.

Turns a Vial keymap (`.vil`) plus its keyboard definition (`vial.json`, a
KLE-style physical layout) into per-key, per-layer legend specs ready to feed
into `key.Key`. Two entry points use this module:

  * `generate_vial.py` -- build and export the caps.

Design decisions (see the repo discussion):
  * A-Z and 0-9 render as *text* (the existing font engine).
  * Everything functional (modifiers, enter/tab/bksp, arrows, media, ...)
    renders as a *Lucide* icon (https://lucide.dev/icons/), fetched on demand
    from the Lucide GitHub raw endpoint and cached locally -- we never vendor
    the whole icon set.
  * Plain typographic symbols (`; , . / - = [ ] ...`) fall back to text of the
    symbol itself: Lucide has no glyph for them and the character reads fine.
  * Four layers map to the four quadrants of the cap: layer 0 is the large
    main legend in the top-left; layers 1/2/3 are small, placed clockwise
    (top-right, bottom-right, bottom-left).
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.request
from dataclasses import dataclass, field

LUCIDE_RAW = "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{name}.svg"
DEFAULT_CACHE = "assets/lucide-cache"


# --------------------------------------------------------------------------- #
# Lucide icon fetching / caching
# --------------------------------------------------------------------------- #

def _ssl_context() -> ssl.SSLContext | None:
    """Trust the agent-proxy CA bundle if one is configured, so HTTPS through
    the sandbox proxy verifies. Falls back to the system store."""
    ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if not ca:
        for cand in ("/root/.ccr/ca-bundle.crt",):
            if os.path.exists(cand):
                ca = cand
                break
    return ssl.create_default_context(cafile=ca) if ca else None


def lucide_svg(name: str, cache_dir: str = DEFAULT_CACHE) -> str:
    """Return a local path to the Lucide icon `name`, downloading it into
    `cache_dir` on first use. Raises on network/HTTP failure."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{name}.svg")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    url = LUCIDE_RAW.format(name=name)
    req = urllib.request.Request(url, headers={"User-Agent": "keycap-gen"})
    with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
        data = resp.read()
    if not data:
        raise RuntimeError(f"empty response fetching Lucide icon '{name}'")
    with open(path, "wb") as f:
        f.write(data)
    return path


# --------------------------------------------------------------------------- #
# Keycode -> legend resolution
# --------------------------------------------------------------------------- #

# Functional keycodes -> Lucide icon name. Extend freely; unknown functional
# keys fall back to a short text label so nothing is silently dropped.
KEYCODE_TO_LUCIDE = {
    "KC_LSFT": "arrow-big-up", "KC_RSFT": "arrow-big-up",
    "KC_LCTL": "chevron-up", "KC_RCTL": "chevron-up",
    "KC_LALT": "option", "KC_RALT": "option",
    "KC_LGUI": "command", "KC_RGUI": "command",
    "KC_ENT": "corner-down-left", "KC_ENTER": "corner-down-left",
    "KC_BSPC": "delete",
    "KC_TAB": "arrow-right-to-line",
    "KC_LEFT": "arrow-left", "KC_DOWN": "arrow-down",
    "KC_UP": "arrow-up", "KC_RGHT": "arrow-right", "KC_RIGHT": "arrow-right",
    "KC_MPLY": "play", "KC_MNXT": "skip-forward", "KC_MPRV": "skip-back",
    "KC_MUTE": "volume-x", "KC_VOLU": "volume-2", "KC_VOLD": "volume-1",
    "KC_BRIU": "sun", "KC_BRID": "sun-dim",
    "KC_PSCR": "camera",
    "KC_HOME": "corner-left-up", "KC_END": "corner-right-down",
    "KC_PGUP": "chevrons-up", "KC_PGDN": "chevrons-down",
    "KC_DEL": "delete",
}

# Functional keycodes with no good icon -> short text label.
KEYCODE_TO_TEXT = {
    "KC_ESC": "Esc", "KC_CAPS": "Caps", "KC_SPC": "", "KC_SPACE": "",
    "KC_INS": "Ins", "KC_APP": "Menu", "KC_PAUS": "Pause", "KC_PSCR": "PrSc",
}
# Function row.
for _n in range(1, 25):
    KEYCODE_TO_TEXT[f"KC_F{_n}"] = f"F{_n}"

# Printable punctuation/symbol keycodes -> the literal character (rendered as
# text). Unshifted symbol only; the shifted glyph is not shown.
KEYCODE_TO_SYMBOL = {
    "KC_MINS": "-", "KC_EQL": "=", "KC_LBRC": "[", "KC_RBRC": "]",
    "KC_BSLS": "\\", "KC_SCLN": ";", "KC_QUOT": "'", "KC_GRV": "`",
    "KC_COMM": ",", "KC_DOT": ".", "KC_SLSH": "/", "KC_NUHS": "#",
    "KC_NUBS": "\\",
    # Shifted symbols (show the symbol itself, not the base key).
    "KC_EXLM": "!", "KC_AT": "@", "KC_HASH": "#", "KC_DLR": "$",
    "KC_PERC": "%", "KC_CIRC": "^", "KC_AMPR": "&", "KC_ASTR": "*",
    "KC_LPRN": "(", "KC_RPRN": ")", "KC_UNDS": "_", "KC_PLUS": "+",
    "KC_LCBR": "{", "KC_RCBR": "}", "KC_PIPE": "|", "KC_COLN": ":",
    "KC_DQUO": '"', "KC_TILD": "~", "KC_LT": "<", "KC_GT": ">",
    "KC_QUES": "?",
}

# "no legend on this layer" sentinels.
_TRANSPARENT = {"KC_TRNS", "KC_TRANSPARENT", "_______", "KC_NO", "XXXXXXX", ""}

# Layer-switch wrappers: MO(1), TG(2), TT(3), DF(0), OSL(1) ...
_LAYER_RE = re.compile(r"^(MO|TG|TT|DF|OSL|TO)\((\d+)\)$")
# Tap wrappers whose tap key we want to show: LT(1, KC_X), LTn(kc), MT(mod, kc).
_LT_NUM_RE = re.compile(r"^LT(\d+)\((KC_\w+)\)$")
_LT_RE = re.compile(r"^LT\(\s*\d+\s*,\s*(KC_\w+)\s*\)$")
_MT_RE = re.compile(r"^MT\(\s*[^,]+,\s*(KC_\w+)\s*\)$")
# Modifier wrappers: LSFT(KC_X), S(KC_X), LCTL(kc) ... show the inner key.
_MOD_RE = re.compile(r"^(?:LSFT|RSFT|LCTL|RCTL|LALT|RALT|LGUI|RGUI|S|C|A|G)\((KC_\w+)\)$")


@dataclass
class Legend:
    """One resolved legend: either text or an icon (by Lucide name)."""
    kind: str          # "text" | "icon"
    value: str         # the character/word, or the Lucide icon name


def resolve_keycode(kc: str) -> Legend | None:
    """Map a Vial keycode to a Legend, or None for transparent/empty keys."""
    if kc is None:
        return None
    kc = kc.strip()
    if kc in _TRANSPARENT:
        return None

    # Unwrap tap/mod/layer-tap wrappers to the underlying tap key.
    for rx in (_LT_RE, _MT_RE, _MOD_RE):
        m = rx.match(kc)
        if m:
            return resolve_keycode(m.group(1))
    m = _LT_NUM_RE.match(kc)
    if m:
        return resolve_keycode(m.group(2))
    m = _LAYER_RE.match(kc)
    if m:
        return Legend("text", f"L{m.group(2)}")

    # Letters and digits -> text.
    if re.fullmatch(r"KC_[A-Z]", kc):
        return Legend("text", kc[3])
    if re.fullmatch(r"KC_[0-9]", kc):
        return Legend("text", kc[3])

    if kc in KEYCODE_TO_LUCIDE:
        return Legend("icon", KEYCODE_TO_LUCIDE[kc])
    if kc in KEYCODE_TO_SYMBOL:
        sym = KEYCODE_TO_SYMBOL[kc]
        return Legend("text", sym) if sym else None
    if kc in KEYCODE_TO_TEXT:
        txt = KEYCODE_TO_TEXT[kc]
        return None if txt == "" else Legend("text", txt)

    # Unknown -> readable text fallback (strip KC_, title-case).
    label = kc[3:] if kc.startswith("KC_") else kc
    label = label.replace("_", " ").title()
    return Legend("text", label[:4])


# --------------------------------------------------------------------------- #
# Quadrant layout
# --------------------------------------------------------------------------- #

@dataclass
class QuadrantSpec:
    """Placement/sizing of the four per-layer legends on a cap. Offsets are
    fractions of the cap footprint; sizes are in mm."""
    ox_frac: float = 0.22     # horizontal quadrant offset (fraction of width)
    oy_frac: float = 0.24     # vertical quadrant offset (fraction of height)
    main_text: float = 4.6    # layer-0 text size
    sub_text: float = 2.5     # layer-1/2/3 text size
    main_icon: float = 5.5    # layer-0 icon target size
    sub_icon: float = 3.2     # layer-1/2/3 icon target size


def quadrant_legends(
    keycodes: list[str | None],
    key_w: float,
    key_h: float,
    spec: QuadrantSpec,
    cache_dir: str = DEFAULT_CACHE,
    fetch: bool = True,
) -> list[dict]:
    """Build the `legends` list for one cap from up to four layer keycodes.

    Quadrant order (clockwise from the large top-left main legend):
        index 0 -> top-left  (large, layer 0)
        index 1 -> top-right (small, layer 1)
        index 2 -> bottom-right (small, layer 2)
        index 3 -> bottom-left  (small, layer 3)
    """
    ox = key_w * spec.ox_frac
    oy = key_h * spec.oy_frac
    positions = [(-ox, oy), (ox, oy), (ox, -oy), (-ox, -oy)]

    legends: list[dict] = []
    for i, kc in enumerate(keycodes[:4]):
        leg = resolve_keycode(kc)
        if leg is None:
            continue
        dx, dy = positions[i]
        is_main = i == 0
        if leg.kind == "icon":
            size = spec.main_icon if is_main else spec.sub_icon
            entry: dict = {"size": size, "dx": dx, "dy": dy}
            if fetch:
                try:
                    entry["svg"] = lucide_svg(leg.value, cache_dir)
                except Exception as ex:
                    print(f"  ! icon '{leg.value}' unavailable ({ex}); "
                          f"skipping", file=sys.stderr)
                    continue
            else:
                entry["icon"] = leg.value  # unresolved; for --emit-layout dumps
            legends.append(entry)
        else:
            size = spec.main_text if is_main else spec.sub_text
            legends.append({"text": leg.value, "size": size, "dx": dx, "dy": dy})
    return legends


# --------------------------------------------------------------------------- #
# Vial keyboard definition (KLE) + keymap (.vil) parsing
# --------------------------------------------------------------------------- #

@dataclass
class PhysKey:
    """A physical key from the board's KLE layout."""
    row: int
    col: int
    x: float
    y: float
    w: float = 1.0
    h: float = 1.0

    @property
    def name(self) -> str:
        return f"r{self.row}c{self.col}"


def parse_board(path: str) -> list[PhysKey]:
    """Parse a Vial keyboard definition (`vial.json`) into physical keys.

    Reads the KLE array at `layouts.keymap`. Each key's matrix position is the
    first line of its label ("row,col"). Standard KLE cursor semantics apply:
    a preceding property object may set `x`/`y` deltas and `w`/`h`; decal keys
    (`d: true`) are skipped. When several layout-option variants share a matrix
    cell, the first occurrence wins (a note is printed for the rest)."""
    with open(path) as f:
        data = json.load(f)
    if "layouts" in data and "keymap" in data["layouts"]:
        rows = data["layouts"]["keymap"]
    elif "keymap" in data:
        rows = data["keymap"]
    else:
        raise ValueError(f"{path}: no 'layouts.keymap' found")

    keys: list[PhysKey] = []
    seen: dict[tuple[int, int], str] = {}
    y = 0.0
    warned_rot = False
    for row in rows:
        x = 0.0
        w = h = 1.0
        for item in row:
            if isinstance(item, dict):
                x += float(item.get("x", 0))
                y += float(item.get("y", 0))
                if "w" in item:
                    w = float(item["w"])
                if "h" in item:
                    h = float(item["h"])
                if any(k in item for k in ("r", "rx", "ry")) and not warned_rot:
                    print("  ! rotated keys in board are placed axis-aligned "
                          "(rotation ignored)", file=sys.stderr)
                    warned_rot = True
                if item.get("d"):
                    item["_decal"] = True  # marker; handled at the string below
                continue
            # item is a key label string.
            label = str(item)
            first = label.split("\n")[0].strip()
            m = re.match(r"^(\d+)\s*,\s*(\d+)$", first)
            if m:
                r, c = int(m.group(1)), int(m.group(2))
                pos = (r, c)
                if pos in seen:
                    print(f"  ! matrix {r},{c} already placed as '{seen[pos]}'"
                          f"; skipping layout-variant duplicate", file=sys.stderr)
                else:
                    seen[pos] = f"r{r}c{c}"
                    keys.append(PhysKey(row=r, col=c, x=x, y=y, w=w, h=h))
            x += w
            w = h = 1.0
        y += 1.0
    return keys


def parse_keymap(path: str) -> list[list[list[str]]]:
    """Parse a `.vil` keymap into `layout[layer][row][col]` of keycode strings."""
    with open(path) as f:
        data = json.load(f)
    layout = data.get("layout")
    if not layout:
        raise ValueError(f"{path}: no 'layout' array in Vial keymap")
    return layout


def keycodes_for(
    layout: list[list[list[str]]], key: PhysKey, layers: int
) -> list[str | None]:
    """The keycodes at `key`'s matrix cell across the first `layers` layers."""
    out: list[str | None] = []
    for L in range(layers):
        try:
            out.append(layout[L][key.row][key.col])
        except (IndexError, KeyError):
            out.append(None)
    return out
