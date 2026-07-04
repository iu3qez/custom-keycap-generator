# Keycap Legends (MMU flush plugs) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-key legend support to `key.py` producing a keycap body with a flush 0.8mm recess plus a separate aligned legend plug body for multi-material (MMU) printing.

**Architecture:** Build the legends as one `Text → extrude` vertical prism ("cutter"). The body is `cap − cutter` (recess); the legend plug is `cutter ∩ outer_profile` (a thin shard whose top follows the cap surface — a single intersection, so no coplanar slivers). `main.py` exports both, aligned, as `<key>.<fmt>` + `<key>.legend.<fmt>`.

**Tech Stack:** Python 3.11, build123d 0.11.1 (OpenCASCADE B-rep), uv, PyYAML. Fonts via fontconfig: Nimbus Sans (text/arrows) + Adwaita Sans (glyphs).

## Global Constraints

- Python 3.11, build123d 0.11.1, run everything via `uv run`.
- build123d exporters are **module-level** (`export_stl`/`export_step`/`export_brep`); 3mf via `Mesher`. Never call `.export_*()` on a `Part`.
- Git commits must **never** include `Co-Authored-By` lines.
- New `KeyConfig` fields must be **defaulted** — `default`, `redox`, `stress_test` layouts stay legend-free and unchanged.
- Glyph set requiring the symbol font: `SYMBOL_GLYPHS = {"⇥", "⌫", "⏎", "⇧"}`. Arrows `← ↓ ↑ →` use the main font.
- Legend defaults: depth 0.8mm, default size 5.5mm, main font `"Nimbus Sans"`, symbol font `"Adwaita Sans"`.
- G20 reference key params (used in test helpers): `key_h=18.0, key_r=1.75, back_slope=front_slope=side_slope=9.5, back_curve=front_curve=0.0, back_dy=6.35, front_dy=5.65, inner_rad=0.3, wall=1.2, tol=tol_tight=0.1`, stem `formal`.
- Tests are plain `assert` scripts run with `uv run python test/<file>.py` (no pytest in this repo). A script exits non-zero (via `assert`) on failure, prints `OK ...` per check.
- Fontconfig prints harmless warnings on stderr; ignore them.

---

### Task 1: Legend data model + font auto-selection

**Files:**
- Modify: `key.py` (add imports, `SYMBOL_GLYPHS`, `KeyConfig` fields, `Key.__init__` wiring, `Key._legend_font_for`)
- Create: `test/_helpers.py`
- Create: `test/test_legend_fonts.py`

**Interfaces:**
- Produces:
  - `key.SYMBOL_GLYPHS: set[str]`
  - `KeyConfig` fields: `legends: list` (default `[]`), `legend_depth: float=0.8`, `legend_size: float=5.5`, `legend_font: str="Nimbus Sans"`, `legend_symbol_font: str="Adwaita Sans"`
  - `Key._legend_font_for(self, text: str, override: str | None = None) -> str`
  - `test/_helpers.py`: `make_key(legends=None, **overrides) -> Key`

- [ ] **Step 1: Write the test helper**

Create `test/_helpers.py`:

```python
"""Shared builders for the plain-assert legend test scripts."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from key import KeyConfig, Key
from stem import stem_from_config

# G20 reference geometry (mirrors configs/styles/g20.yaml)
_G20 = dict(
    tol=0.1, tol_tight=0.1, wall=1.2, inner_rad=0.3,
    key_h=18.0, key_r=1.75,
    back_slope=9.5, front_slope=9.5, side_slope=9.5,
    back_curve=0.0, front_curve=0.0,
    back_dy=6.35, front_dy=5.65, width=1.0,
)

def make_key(legends=None, **overrides):
    cfg = dict(_G20)
    cfg.update(overrides)
    if legends is not None:
        cfg["legends"] = legends
    return Key(KeyConfig(**cfg), stem_from_config(type="formal"))
```

- [ ] **Step 2: Write the failing test**

Create `test/test_legend_fonts.py`:

```python
from _helpers import make_key
from key import SYMBOL_GLYPHS

def test_symbol_glyph_set():
    assert SYMBOL_GLYPHS == {"⇥", "⌫", "⏎", "⇧"}

def test_font_auto_selection():
    k = make_key(legends=[])
    assert k._legend_font_for("Q") == "Nimbus Sans"     # letter -> main
    assert k._legend_font_for("←") == "Nimbus Sans"     # arrow -> main
    assert k._legend_font_for("⇥") == "Adwaita Sans"    # glyph -> symbol
    assert k._legend_font_for("⌫") == "Adwaita Sans"

def test_font_override():
    k = make_key(legends=[])
    assert k._legend_font_for("⇥", "Custom Sans") == "Custom Sans"

def test_config_defaults():
    k = make_key(legends=[])
    assert k.legend_depth == 0.8
    assert k.legend_size == 5.5
    assert k.legend_font == "Nimbus Sans"
    assert k.legend_symbol_font == "Adwaita Sans"
    assert k.legends == []

if __name__ == "__main__":
    test_symbol_glyph_set(); print("OK symbol glyph set")
    test_font_auto_selection(); print("OK font auto-selection")
    test_font_override(); print("OK font override")
    test_config_defaults(); print("OK config defaults")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run python test/test_legend_fonts.py`
Expected: FAIL — `ImportError: cannot import name 'SYMBOL_GLYPHS'` (or `TypeError` on unknown `KeyConfig` field).

- [ ] **Step 4: Implement the data model + font selection**

In `key.py`, add the import near the top (after `from dataclasses import dataclass`):

```python
from functools import cached_property
```

Add above the `KeyConfig` dataclass:

```python
SYMBOL_GLYPHS = {"⇥", "⌫", "⏎", "⇧"}
```

Add these fields to `KeyConfig`, **after** `bump: bool = False` (defaulted fields must come last):

```python
    legends: list = field(default_factory=list)
    legend_depth: float = 0.8
    legend_size: float = 5.5
    legend_font: str = "Nimbus Sans"
    legend_symbol_font: str = "Adwaita Sans"
```

Add `field` to the dataclasses import at the top of `key.py`:

```python
from dataclasses import dataclass, field
```

In `Key.__init__`, after `self.bump = config.bump`, wire the new config:

```python
        self.legends = config.legends
        self.legend_depth = config.legend_depth
        self.legend_size = config.legend_size
        self.legend_font = config.legend_font
        self.legend_symbol_font = config.legend_symbol_font
```

Add the method to `Key` (e.g. after `__init__`):

```python
    def _legend_font_for(self, text: str, override: str | None = None) -> str:
        """Pick the font for a legend: explicit override, else the symbol font
        for keyboard glyphs, else the main font."""
        if override:
            return override
        if any(ch in SYMBOL_GLYPHS for ch in text):
            return self.legend_symbol_font
        return self.legend_font
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python test/test_legend_fonts.py`
Expected: PASS — prints four `OK ...` lines, exit 0.

- [ ] **Step 6: Commit**

```bash
git add key.py test/_helpers.py test/test_legend_fonts.py
git commit -m "feat: add legend config fields and font auto-selection"
```

---

### Task 2: Legend cutter, recessed body, and plug

**Files:**
- Modify: `key.py` (add `Key._legend_cutter`, `Key.legend_plug`; modify `Key.shape`)
- Create: `test/test_legend_geometry.py`

**Interfaces:**
- Consumes: `make_key` (Task 1); `KeyConfig` legend fields; `Key._legend_font_for`.
- Produces:
  - `Key._legend_cutter` — `cached_property` returning `Part | None` (None when no legends).
  - `Key.legend_plug(self) -> Part | None`.
  - `Key.shape` now subtracts the cutter when present.

- [ ] **Step 1: Write the failing test**

Create `test/test_legend_geometry.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python test/test_legend_geometry.py`
Expected: FAIL — `AttributeError: 'Key' object has no attribute '_legend_cutter'` (or `legend_plug`).

- [ ] **Step 3: Implement the cutter, recess, and plug**

In `key.py`, add the cutter as a cached property on `Key`:

```python
    @cached_property
    def _legend_cutter(self) -> "Part | None":
        """Vertical prism of the legend glyphs, flat-bottomed at `z_floor`,
        tall enough to pass above the cap top. Subtracting it carves the recess;
        intersecting it with the outer profile yields the flush plug."""
        if not self.legends:
            return None

        # Top-surface height at the key center; the flat cutter floor sits
        # `legend_depth` below it (recess depth ~uniform on the near-flat top).
        h_center = (self.front_dy + self.back_dy) / 2.0
        z_floor = h_center - self.legend_depth
        z_top = self.max_height + 1.0            # safely above the tallest corner

        with BuildPart() as cutter:
            with BuildSketch(Plane.XY.offset(z_floor)):
                for leg in self.legends:
                    text = leg["text"]
                    size = leg.get("size", self.legend_size)
                    dx = leg.get("dx", 0.0)
                    dy = leg.get("dy", 0.0)
                    font = self._legend_font_for(text, leg.get("font"))
                    with Locations((dx, dy)):
                        Text(text, font_size=size, font=font)
            extrude(amount=z_top - z_floor)
        return cutter.part

    def legend_plug(self) -> "Part | None":
        """The flush legend plug (material 2): the cutter clipped by the solid
        outer profile, so its top follows the cap surface exactly."""
        cutter = self._legend_cutter
        if cutter is None:
            return None
        return cutter & self._outer_key_profile()
```

In `Key.shape`, subtract the cutter at the very end, just before `return shape`:

```python
        # Carve the legend recess (material 1). Done last so it cuts through the
        # finished top surface; a no-op when the key has no legends.
        if self._legend_cutter is not None:
            shape = shape - self._legend_cutter

        return shape
```

(Note: `Text`, `Locations`, `extrude`, `BuildSketch`, `BuildPart`, `Plane` all come from the existing `from build123d import *`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python test/test_legend_geometry.py`
Expected: PASS — four `OK ...` lines. (Fontconfig warnings on stderr are fine.)

- [ ] **Step 5: Commit**

```bash
git add key.py test/test_legend_geometry.py
git commit -m "feat: build legend cutter, recessed body, and flush plug"
```

---

### Task 3: Planck POC layout

**Files:**
- Create: `configs/layouts/planck_poc.yaml`
- Modify: `test/_helpers.py` (add `build_from_layout`)
- Create: `test/test_poc_layout.py`

**Interfaces:**
- Consumes: `KeyConfig`, `Key`, `stem_from_config`.
- Produces: `test/_helpers.py: build_from_layout(layout_name, style_name="g20") -> dict[str, Key]`.

- [ ] **Step 1: Create the POC layout**

Create `configs/layouts/planck_poc.yaml`:

```yaml
# Proof-of-concept layout for legend support. Five keys covering every case:
# single letter, word, dual stacked ANSI pair, keyboard glyph, and a blank 2u.
# The full 48-key Planck legend map is a follow-up.

keys:
  q:                                  # single letter (default size 5.5)
    base: G20
    legends:
      - {text: "Q"}
  esc:                                # word legend, smaller
    base: G20
    legends:
      - {text: "Esc", size: 3.5}
  semicolon:                          # dual ANSI stacked (base low, shift high)
    base: G20
    legends:
      - {text: ";", size: 4.0, dy: -1.0}
      - {text: ":", size: 4.0, dy: 1.0}
  tab:                                # keyboard glyph -> Adwaita Sans (auto)
    base: G20
    legends:
      - {text: "⇥"}
  space2u:                            # 2u spacebar, no legend -> one file, no plug
    base: G20
    width: 2.0
```

- [ ] **Step 2: Write the failing test**

Add to `test/_helpers.py` (append at the end):

```python
import yaml

def build_from_layout(layout_name, style_name="g20"):
    """Merge style+layout exactly like main.py and return {key_name: Key}."""
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(_here, f"configs/styles/{style_name}.yaml")) as f:
        style = yaml.safe_load(f)
    with open(os.path.join(_here, f"configs/layouts/{layout_name}.yaml")) as f:
        layout = yaml.safe_load(f)

    keys = {}
    for name, kc in layout["keys"].items():
        base = kc.pop("base", "")
        mods = kc.pop("modifiers", [])
        cfg = style["global"] | style["bases"].get(base, {}) | kc
        for m in mods:
            cfg = cfg | style["modifiers"][m]
        stem = stem_from_config(**cfg.pop("stem", {}))
        keys[name] = Key(KeyConfig(**cfg), stem)
    return keys
```

Create `test/test_poc_layout.py`:

```python
from _helpers import build_from_layout

def test_poc_keys_present():
    keys = build_from_layout("planck_poc")
    assert set(keys) == {"q", "esc", "semicolon", "tab", "space2u"}

def test_every_key_builds():
    keys = build_from_layout("planck_poc")
    for name, k in keys.items():
        assert k.shape().volume > 0, name

def test_plug_presence():
    keys = build_from_layout("planck_poc")
    assert keys["q"].legend_plug() is not None
    assert keys["esc"].legend_plug() is not None
    assert keys["semicolon"].legend_plug() is not None
    assert keys["tab"].legend_plug() is not None
    assert keys["space2u"].legend_plug() is None      # blank 2u -> no plug

def test_dual_legend_has_more_volume_than_single():
    # the stacked ; : plug must carve more than a single-char ; plug
    from _helpers import make_key
    keys = build_from_layout("planck_poc")
    dual_v = keys["semicolon"].legend_plug().volume
    single_v = make_key(legends=[{"text": ";", "size": 4.0}]).legend_plug().volume
    assert dual_v > single_v

if __name__ == "__main__":
    test_poc_keys_present(); print("OK poc keys present")
    test_every_key_builds(); print("OK every key builds")
    test_plug_presence(); print("OK plug presence")
    test_dual_legend_has_more_volume_than_single(); print("OK dual legend")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run python test/test_poc_layout.py`
Expected: FAIL — `ImportError: cannot import name 'build_from_layout'`.

- [ ] **Step 4: Implement**

The implementation is the `build_from_layout` helper and the layout file from Steps 1–2. No further code needed.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python test/test_poc_layout.py`
Expected: PASS — four `OK ...` lines.

- [ ] **Step 6: Commit**

```bash
git add configs/layouts/planck_poc.yaml test/_helpers.py test/test_poc_layout.py
git commit -m "feat: add Planck POC legend layout"
```

---

### Task 4: MMU export (two aligned files per legended key)

**Files:**
- Modify: `main.py` (factor an `export_shape` helper; export the plug as a second file)
- Create: `test/test_mmu_export.py`

**Interfaces:**
- Consumes: `Key.shape`, `Key.legend_plug`; the `planck_poc` layout.
- Produces: for each legended key, files `<key>.<fmt>` and `<key>.legend.<fmt>`; legend-free keys produce only `<key>.<fmt>`.

- [ ] **Step 1: Write the failing test**

Create `test/test_mmu_export.py`:

```python
import os, sys, subprocess, tempfile

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _render(outdir):
    r = subprocess.run(
        ["uv", "run", "python", "main.py", "g20", "planck_poc", "-o", outdir],
        cwd=_HERE, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return outdir

def test_legended_key_has_two_files():
    with tempfile.TemporaryDirectory() as d:
        _render(d)
        assert os.path.exists(os.path.join(d, "q.stl"))
        assert os.path.exists(os.path.join(d, "q.legend.stl"))

def test_blank_key_has_one_file():
    with tempfile.TemporaryDirectory() as d:
        _render(d)
        assert os.path.exists(os.path.join(d, "space2u.stl"))
        assert not os.path.exists(os.path.join(d, "space2u.legend.stl"))

if __name__ == "__main__":
    test_legended_key_has_two_files(); print("OK legended key -> 2 files")
    test_blank_key_has_one_file(); print("OK blank key -> 1 file")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python test/test_mmu_export.py`
Expected: FAIL — `AssertionError` on the missing `q.legend.stl` (main.py doesn't emit plugs yet).

- [ ] **Step 3: Implement the export helper + plug output**

In `main.py`, replace the current per-key export block:

```python
        out_path = os.path.join(args.output_path, f"{key_name}.{args.format}")
        shape = key.shape()
        if args.format == 'stl':
            export_stl(shape, out_path)
        elif args.format == 'brep':
            export_brep(shape, out_path)
        elif args.format == 'step':
            export_step(shape, out_path)
        elif args.format == '3mf':
            mesher = Mesher(unit=Unit.MM)
            mesher.add_shape(shape, linear_deflection=1e-3, angular_deflection=0.1)
            mesher.write(out_path)
```

with a factored helper plus the plug output:

```python
        def export_shape(shape, path):
            if args.format == 'stl':
                export_stl(shape, path)
            elif args.format == 'brep':
                export_brep(shape, path)
            elif args.format == 'step':
                export_step(shape, path)
            elif args.format == '3mf':
                mesher = Mesher(unit=Unit.MM)
                mesher.add_shape(shape, linear_deflection=1e-3, angular_deflection=0.1)
                mesher.write(path)

        base_path = os.path.join(args.output_path, f"{key_name}.{args.format}")
        export_shape(key.shape(), base_path)                 # material 1

        plug = key.legend_plug()
        if plug is not None:                                  # material 2
            plug_path = os.path.join(
                args.output_path, f"{key_name}.legend.{args.format}"
            )
            export_shape(plug, plug_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python test/test_mmu_export.py`
Expected: PASS — two `OK ...` lines.

- [ ] **Step 5: Commit**

```bash
git add main.py test/test_mmu_export.py
git commit -m "feat: export legend plug as separate MMU body"
```

---

### Task 5: Render + visual verification and tuning

**Files:**
- None created; produces preview PNGs under the scratchpad and (optionally) tuned values in `configs/layouts/planck_poc.yaml`.

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Render the POC set**

Run:
```bash
uv run python main.py g20 planck_poc -o output
ls output/
```
Expected files: `q.stl`, `q.legend.stl`, `esc.stl`, `esc.legend.stl`, `semicolon.stl`, `semicolon.legend.stl`, `tab.stl`, `tab.legend.stl`, `space2u.stl` (and **no** `space2u.legend.stl`).

- [ ] **Step 2: Preview body + plug together (two colours)**

For each legended key, render body and plug in one OpenSCAD scene from a top angle:
```bash
SCR="$SCRATCH"   # session scratchpad dir
for k in q esc semicolon tab; do
  printf 'color("SteelBlue") import("%s/output/%s.stl");\ncolor("Ivory") import("%s/output/%s.legend.stl");\n' \
    "$PWD" "$k" "$PWD" "$k" > "$SCR/$k.scad"
  DISPLAY=:1 openscad -o "$SCR/preview_$k.png" --imgsize=900,700 \
    --colorscheme=Tomorrow --autocenter --viewall --camera=0,0,0,55,0,25,0 \
    "$SCR/$k.scad" 2>&1 | grep -i "rendering time"
done
```
Then Read each `preview_$k.png`.

- [ ] **Step 3: Check the acceptance criteria visually**

Confirm on the previews:
- Legends sit **flush** with the cap top (plug top follows the surface, no gap, no proud shard).
- Glyph `tab` shows a real `⇥`, not tofu / empty box.
- `semicolon` shows `;` low and `:` high, both centered horizontally, not overlapping.
- `esc` fits within the top face (not spilling over the taper).
- Letters are crisp with no sliver artifacts around the glyph edges.

- [ ] **Step 4: Tune if needed**

If a legend is mis-sized, off-center, too shallow/deep, or spills over the taper, adjust the offending key's `legends` entry (`size`, `dx`, `dy`) or the `legend_depth`/`legend_size` defaults in `configs/styles/g20.yaml` (add a `global:` entry to override), then re-run Steps 1–3. Re-run the geometry tests after any change:
```bash
uv run python test/test_legend_geometry.py
uv run python test/test_poc_layout.py
```

- [ ] **Step 5: Commit any tuning**

```bash
git add configs/layouts/planck_poc.yaml configs/styles/g20.yaml
git commit -m "chore: tune POC legend sizing/depth from render"
```
(Skip if no tuning was necessary.)

---

## Self-Review

**Spec coverage:**
- MMU body + separate flush plug → Tasks 2 (geometry) + 4 (export). ✓
- `Text → extrude → intersect`, flat-bottomed cutter → Task 2 `_legend_cutter`/`legend_plug`. ✓
- Hybrid Nimbus/Adwaita + auto glyph font → Task 1 `_legend_font_for` + `SYMBOL_GLYPHS`. ✓
- Data model (`legends` entries: text/size/dx/dy/font; depth/size/font defaults) → Task 1. ✓
- POC 5 keys (single/word/dual/glyph/blank-2u) → Task 3 `planck_poc.yaml`. ✓
- `body + plug` reconstructs smooth cap → Task 2 invariant test. ✓
- `space2u` → one file, no plug → Tasks 3 + 4 tests. ✓
- Verification render loop → Task 5. ✓
- Backward compatibility (defaulted fields) → Global Constraints + Task 1 defaults. ✓

**Placeholder scan:** No TBD/TODO; all code shown in full; commands have expected output. ✓

**Type consistency:** `_legend_cutter` (cached_property, `Part | None`), `legend_plug()` (`Part | None`), `_legend_font_for(text, override=None)`, `make_key(legends=None, **overrides)`, `build_from_layout(layout_name, style_name="g20")` — names/signatures used consistently across Tasks 1–4. ✓
