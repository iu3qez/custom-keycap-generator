# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is / why this fork exists

A parametric **keycap** generator built on **build123d** (OpenCASCADE B-rep kernel), forked
from `nicola-sorace/custom-keycap-generator`. Each keycap is a Python-built solid exported to
STL/STEP/3MF/BREP — no meshing/CSG fragility.

**Goal for this fork:** generate a full **Planck 40% (4×12 ortholinear) keycap set in a uniform
G20-style profile with per-key legends**, ideally as separate legend bodies for multi-material
(MMU) printing. We came here after hitting OpenSCAD/KeyV2 limits (coplanar-boolean sliver
artifacts on flush legend plugs, `$`-variable propagation quirks). The B-rep kernel makes the
legend plug a clean `Text → extrude → intersect(cap)` instead of a fragile mesh difference.

> **Known gap:** upstream has **no legend/text support**. Adding legends to `key.py` is the main
> work item here (see "Extending" below).

## Environment & commands

Uses **uv** (Python 3.11). Deps are declared in `pyproject.toml` (`uv sync` writes `uv.lock`).

```bash
uv sync                                   # create .venv and install (build123d/OCP wheels are large)
uv run python main.py <style> <layout>    # generate a set -> output/<key_name>.<fmt>
uv run python main.py default redox -f 3mf -o output   # example, 3mf format
uv run python visualize.py                # live-preview ONE key via ocp_vscode `show()`
```

- Formats: `stl` (default), `brep`, `step`, `3mf` (`-f/--format`), output dir via `-o`.
- Config lives in `configs/styles/<style>.yaml` and `configs/layouts/<layout>.yaml`; `main.py`
  loads them **by bare name** (no path, no extension).
- There is **no build/lint step and no real test suite** — `test/` and the `stress_test` layout
  are ad-hoc geometry checks. "Testing" = render a key and inspect it.
- `ocp_vscode` emits Fontconfig warnings on stderr; they are harmless.

## Architecture

Three-file pipeline, all `from build123d import *`:

- **`main.py`** — the runner. Merges config dicts in priority order
  `style.global | style.bases[base] | key_conf | style.modifiers[*]`, pops the `stem` sub-dict,
  builds a `KeyConfig` + `Stem`, then exports **one file per key** in the layout. Note it uses
  plain `dict |` merge, so a key's inline options override its base, and **modifiers override
  everything** (applied last).
- **`key.py`** — `KeyConfig` (dataclass of all tunables) and `Key`. `Key.shape()` is the whole
  geometry: build a solid trapezoidal-prism outer profile (`_outer_key_profile`, via the
  **intersection of two lofts** — one along X, one along Y — with optional curved front/back tops
  and corner `fillet`), shell it by subtracting a `shift=-wall` copy of that same profile
  (deliberately **avoids build123d `offset`**, called unreliable), fill the top block so the stem
  is short, add the stem, then optionally `fillet` inner edges and add a homing `bump`.
- **`stem.py`** — `stem_from_config(type=...)` → `StemFormal` (standard Cherry MX cross),
  `StemReinforced` (adds a rounded rectangle of material), `StemMinimal` (default in the shipped
  style; thin-wall variant, "not recommended"). Cherry dims live in the `Stem` dataclass.

### Profiles & the G20 goal

There are **no named profiles**; a "profile" is just per-row `back_dy`/`front_dy` (back/front
top heights) plus `back_slope`/`front_slope`/`side_slope` and `back_curve`/`front_curve` (a
`ThreePointArc` dish; negative = convex, as the `convex` modifier does). Rows `R1..R4` in
`configs/styles/default.yaml` are **sculpted** (heights differ per row).

For a **uniform G20-style set**, make every base identical — one low, flat base
(`back_dy == front_dy`, small; slopes/curves near-flat), so all 1u keys are geometrically the
same. Consequence: the "set" only needs a couple of distinct models (**one 1u + one 2u**), each
printed in multiple copies. Stem should be `formal` (the default `minimal` is discouraged).

## Extending: legends (the main TODO)

`Key.shape()` has no text. To add flush legends per key:
1. Add legend fields to `KeyConfig` (e.g. `legends: list`, size, font — hybrid font note below).
2. Build the legend solid with `Text(...)` → `extrude`, positioned at the cap's top surface,
   then **`intersect` with the cap solid** to get a clean flush plug (top follows the cap, no
   coplanar-difference slivers).
3. For MMU: return/export the legend plug as a **separate body** aligned to the cap (subtract the
   plug from the cap for material 1, export the plug for material 2).
4. Font caveat carried over from the OpenSCAD work: most sans fonts lack the keyboard glyphs
   `⇥ ⌫ ⏎ ⇧`; use a hybrid — a nice sans (e.g. Nimbus Sans) for text, DejaVu only for those glyphs.

## Related prior work

The original Planck/G20 target and the desired legend behaviour (gap-aware 13-col Planck layout,
stacked ANSI dual legends on punctuation `;: ,< .> /?`, 2u spacebar, hybrid Nimbus/DejaVu fonts)
were prototyped in OpenSCAD in the sibling repo `../KeyV2` (`planck_g20.scad`). Reuse those
decisions when building the build123d equivalent.
