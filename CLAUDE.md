# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is / why this fork exists

A parametric **keycap** generator built on **build123d** (OpenCASCADE B-rep kernel), forked
from `nicola-sorace/custom-keycap-generator`. Each keycap is a Python-built solid exported to
STL/STEP/3MF/BREP — no meshing/CSG fragility.

**Goal for this fork (DONE):** generate a full **Planck 40% (4×12 ortholinear) keycap set in a
uniform G20-style profile with per-key legends**, as separate legend bodies for multi-material
(MMU) printing. We came here after hitting OpenSCAD/KeyV2 limits (coplanar-boolean sliver
artifacts on flush legend plugs, `$`-variable propagation quirks). The B-rep kernel makes the
legend plug a clean `Text → extrude → intersect(cap)` instead of a fragile mesh difference.

The G20 profile (`configs/styles/g20.yaml`), the legend engine in `key.py`, the full 46-key
`configs/layouts/planck.yaml`, a per-key stem support-blocker modifier, and multi-object 3mf
export are all implemented. See "Legends & MMU export" below. Upstream still has no text support;
that is this fork's addition.

Design docs live in `docs/superpowers/specs/` and `docs/superpowers/plans/`.

## Environment & commands

Uses **uv** (Python 3.11). Deps are declared in `pyproject.toml` (`uv sync` writes `uv.lock`).

```bash
uv sync                                   # create .venv and install (build123d/OCP wheels are large)
uv run python main.py g20 planck          # full Planck G20 set -> output/ (STL)
uv run python main.py g20 planck -f 3mf   # one multi-object 3mf per key (body+legend+stem)
uv run python main.py g20 planck_poc      # 5-key proof-of-concept (one per legend case)
uv run python assemble.py g20 planck      # whole set in ONE STEP -> output/planck.step
uv run python visualize.py                # live-preview ONE key via ocp_vscode `show()`
uv run python generate_vial.py g20 keymap.vil -f 3mf              # set from a Vial keymap (ortho)
```

- Formats: `stl` (default), `brep`, `step`, `3mf` (`-f/--format`), output dir via `-o`.
- **Outputs per key:** `<key>.<fmt>` (body, material 1), `<key>.legend.<fmt>` (flush legend plug,
  material 2 — only if the key has legends), `<key>.stem.<fmt>` (slicer support-blocker modifier).
  In `3mf` mode these are **bundled into one multi-object `<key>.3mf`** (named objects); in
  stl/step/brep they are separate files.
- Config lives in `configs/styles/<style>.yaml` and `configs/layouts/<layout>.yaml`; `main.py`
  loads them **by bare name** (no path, no extension).
- **Tests** are plain `assert` scripts under `test/` (no pytest): `uv run python test/<file>.py`
  prints `OK ...` per check. `test_legend_*`, `test_poc_layout`, `test_stem_guard` are fast unit
  checks; `test_vial` covers the Vial parser/keycode-resolver/quadrant layout (offline, no icon
  fetch); `test_mmu_export` renders the POC set (slower, subprocess). Beyond these, "testing" =
  render a key and inspect it. No build/lint step.
- `ocp_vscode`/fontconfig emit warnings on stderr; they are harmless.

## Architecture

Three-file pipeline, all `from build123d import *`:

- **`main.py`** — the runner. Merges config dicts in priority order
  `style.global | style.bases[base] | key_conf | style.modifiers[*]`, pops the `stem` sub-dict,
  builds a `KeyConfig` + `Stem`, then exports each key's bodies (`shape()`, `legend_plug()`,
  `stem_guard()`). In `3mf` mode it bundles them into one multi-object file via `Mesher`
  (`export_3mf_multi`, `part_number` = object name); otherwise one file per body. Note the plain
  `dict |` merge: a key's inline options override its base, and **modifiers override everything**
  (applied last). build123d exporters are **module-level** functions (`export_stl/step/brep`); 3mf
  uses `Mesher` — never `.export_*()` on a `Part`.
- **`key.py`** — `KeyConfig` (dataclass of all tunables, incl. `legends`/`legend_depth`/
  `legend_size`/`legend_font`/`legend_symbol_font`, all defaulted) and `Key`. `Key.shape()` is the
  whole geometry: build a solid trapezoidal-prism outer profile (`_outer_key_profile`, via the
  **intersection of two lofts** — one along X, one along Y — with optional curved front/back tops
  and corner `fillet`), shell it by subtracting a `shift=-wall` copy of that same profile
  (deliberately **avoids build123d `offset`**, called unreliable), fill the top block so the stem
  is short, add the stem, optionally `fillet` inner edges and add a homing `bump`, then **subtract
  the legend cutter** to carve the recess. `legend_plug()` and `stem_guard()` return the two extra
  bodies (see "Legends & MMU export"). A legend entry is `{text: …}` **or** `{svg: <path>, …}`;
  SVG legends go through `svg_legend_sketch` (module-level, `@lru_cache`d): `import_svg` → fill
  closed wires, inflate open strokes into ribbons via `offset(side=Side.BOTH)` (build123d `trace`
  **segfaults** the OCP kernel — do not use it), then center + mirror-Y + scale to `size`.
- **`vial.py`** — Vial → legends. `parse_board` reads a keyboard's KLE layout (`layouts.keymap`)
  into physical keys (matrix pos + width from standard KLE cursor rules); `board_from_keymap`
  derives the same grid straight from a `.vil` matrix when no board file is given (each populated
  cell = 1u; an interior `-1` gap is absorbed by the key to its right → 2u spacebar). `parse_keymap`
  reads a `.vil` into `layout[layer][row][col]` (values are keycode strings or `-1`).
  `resolve_keycode` maps a keycode to text or a Lucide icon name (A-Z/0-9 & typographic/keypad
  symbols → text; functional keys → `KEYCODE_TO_LUCIDE`/`RM_TO_LUCIDE`; `KC_ALIASES` folds long QMK
  spellings to short; transparent/`-1` → None; tap/mod/layer wrappers unwrapped). `quadrant_legends`
  places up to four layers clockwise from the large top-left main (`QuadrantSpec` holds
  sizes/offsets). `lucide_svg` fetches icons from Lucide's GitHub raw endpoint into
  `assets/lucide-cache/` (gitignored) via urllib + the proxy CA bundle.
- **`generate_vial.py`** — runner: `style + keymap.vil [--board board.json]` → one cap per physical
  key, same three exported bodies as `main.py`. `--emit-layout` dumps the computed keys as a layout
  YAML; `--base`/`--layers`/`--glyph-dir` tune the run.
- **`assemble.py`** — separate entry point that lays every key out at its grid position (from the
  layout's top-level `grid:` section, `UNIT = 19mm/unit`) and writes the whole set as **one
  multi-solid STEP** (`output/<layout>.step`), each solid labeled `<key>` / `<key>.legend` /
  `<key>.stem`. A CAD preview/archive of the full set; `main.py` is unaffected (it reads only
  `keys:`, ignoring `grid:`).
- **`stem.py`** — `stem_from_config(type=...)` → `StemFormal` (standard Cherry MX cross),
  `StemReinforced` (adds a rounded rectangle of material), `StemMinimal` (default in the shipped
  style; thin-wall variant, "not recommended"). Cherry dims live in the `Stem` dataclass.

### Profiles & the G20 goal

There are **no named profiles**; a "profile" is just per-row `back_dy`/`front_dy` (back/front
top heights) plus `back_slope`/`front_slope`/`side_slope` and `back_curve`/`front_curve` (a
`ThreePointArc` dish; negative = convex, as the `convex` modifier does). Rows `R1..R4` in
`configs/styles/default.yaml` are **sculpted** (heights differ per row).

The **G20 set** (`configs/styles/g20.yaml`) is one uniform low base: flat top (`back_curve ==
front_curve == 0`), 1.75mm edge radius, ~9.5° taper, and a 2.5° micro-tilt baked in via
`back_dy 6.35 / front_dy 5.65` (avg 6.0mm), ported from `../KeyV2/src/key_profiles/g20.scad`.
`inner_rad` is capped at 0.3 (larger fails to fillet on the low top). Stem is `formal`. Because
the geometry is uniform, all 1u keys are identical *shape*; the per-key **legends** are what make
each key a distinct model, so `configs/layouts/planck.yaml` enumerates all 46 keys.

## Legends & MMU export

Implemented in `key.py` (approach A: `Text → extrude → intersect`):

- `_legend_cutter` (cached) builds a flat-bottomed vertical prism of all the key's `Text` glyphs,
  floored `legend_depth` (0.8mm) below the top-center height. `shape()` subtracts it → the recess.
- `legend_plug()` = `cutter & _outer_key_profile()` → a thin flush plug whose top follows the cap
  surface exactly (a single intersection, so **no coplanar slivers** — the thing OpenSCAD couldn't
  do). `body + plug` reconstructs the smooth cap (verified to ~0.008 mm³).
- `stem_guard()` = a plain cylinder the size of the Cherry tube (`stem.stem_rad`, height
  `stem_depth`, from z=0) that fills the stem's inner cross. Load it in the slicer as a **modifier
  volume with supports disabled** so no supports print inside the cross. Not printed as material.
- **Fonts** (hybrid, `_legend_font_for` auto-selects): **Nimbus Sans** for text/arrows,
  **Adwaita Sans** for the keyboard glyphs `⇥ ⌫ ⏎ ⇧` (`SYMBOL_GLYPHS`). KeyV2 used DejaVu, but
  DejaVu is not installed here — Adwaita covers those four glyphs. Per-legend `font` overrides.
- **Layout legend spec** (per key, in the layout YAML): `legends: [{text, size, dx, dy, font}]`.
  Words (Esc/Ctl/…) use `size: 3.5`; ANSI dual pairs `;: ,< .> /?` are two stacked entries at
  `size: 4.0, dy: ±1.2`. Quote `"y"`/`"n"` layout keys so PyYAML doesn't read them as booleans.

MMU workflow: import a key's `.3mf` (or its 3 STLs), assign material 1 to the body, material 2 to
the `.legend` object(s), and mark the `.stem` object as a no-support modifier. (In 3mf, a legend
with disconnected glyphs like "Esc" appears as several same-named `<key>.legend` objects — all one
material.)

## Related prior work

The original Planck/G20 target and the legend behaviour (Planck layout, stacked ANSI dual legends
on punctuation `;: ,< .> /?`, 2u spacebar, hybrid fonts) were prototyped in OpenSCAD in the
sibling repo `../KeyV2` (`planck_g20.scad`, `src/key_profiles/g20.scad`). Those decisions are now
ported here; consult KeyV2 when tuning legend content or the G20 profile.
