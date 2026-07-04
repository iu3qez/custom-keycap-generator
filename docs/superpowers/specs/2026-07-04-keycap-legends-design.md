# Keycap legends (MMU flush plugs) — design

Date: 2026-07-04
Status: approved (proof-of-concept scope)

## Goal

Add per-key legend support to `key.py` so a keycap can carry text/glyph legends,
produced as a **separate flush legend body** for multi-material (MMU) printing:

- **Material 1** — keycap body with a 0.8mm recess in the shape of the legends.
- **Material 2** — a thin flush plug that fills that recess, its top following the
  cap's top surface exactly.

This is the main work item of the fork (upstream has no text support) and the
thing OpenSCAD/KeyV2 could not do cleanly: the flush plug there was
`difference(smooth_cap, recessed_cap)`, which left coplanar sliver shards. The
B-rep kernel lets us build the plug as a single `intersect`, avoiding that class
of failure.

## Scope

**Proof-of-concept first.** Implement the legend machinery in `key.py` and
validate it on a handful of representative keys before scaling to the full
48-key Planck set. The POC exercises every legend case in one layout:

| Key       | Case                | Legend(s)                          |
|-----------|---------------------|------------------------------------|
| `q`       | single letter       | "Q", size 5.5                      |
| `esc`     | word (smaller)      | "Esc", size 3.5                    |
| `semicolon` | dual ANSI stacked | ";" low + ":" high, size 4, dy ±1.0 |
| `tab`     | keyboard glyph      | "⇥" (Adwaita Sans, auto-selected)  |
| `space2u` | no legend, 2u       | none → single file, no plug        |

The full-set Planck legend map (from `../KeyV2/planck_g20.scad`) is out of scope
for this spec; it becomes a follow-up once the POC is validated.

## Fonts

Hybrid, using fonts installed on this system (KeyV2's DejaVu Sans Mono is not
installed here):

- **Text and arrows** (`← ↓ ↑ →` render fine): **Nimbus Sans** (`/usr/share/fonts/gsfonts`).
- **Keyboard glyphs** `⇥ ⌫ ⏎ ⇧` (absent from Nimbus): **Adwaita Sans** (installed,
  covers all four).

`key.py` holds the glyph set `SYMBOL_GLYPHS = {"⇥", "⌫", "⏎", "⇧"}` and auto-selects
`legend_symbol_font` for those characters, `legend_font` otherwise. A per-legend
`font` field overrides the auto choice.

Both fonts verified to render geometry via build123d `Text` on this system.

## Data model

New `KeyConfig` fields (all defaulted → backward compatible with `default`,
`redox`, `stress_test`, which stay legend-free):

```python
legends: list = field(default_factory=list)   # per-key, from layout YAML
legend_depth: float = 0.8                       # recess / plug depth (mm)
legend_size: float = 5.5                        # default when a legend omits size
legend_font: str = "Nimbus Sans"                # text + arrows
legend_symbol_font: str = "Adwaita Sans"        # glyphs ⇥ ⌫ ⏎ ⇧
```

A legend entry (dict in the layout YAML):

- `text` (required) — the string to render.
- `size` (default `legend_size`) — font size in mm.
- `dx`, `dy` (default 0) — offset in mm on the top face (`+dy` toward the back).
- `font` (optional) — override; if omitted, auto-selected (Adwaita for glyphs,
  Nimbus otherwise).

Offsets are direct millimetres (not KeyV2's normalized `pos`), for readability.

Config flow (`main.py` merge): `legends` comes from the per-key layout entry;
`legend_depth`/fonts/`legend_size` come from the style `global` (or dataclass
defaults). `KeyConfig(**config)` tolerates missing keys (defaults) and the extra
`legends` list passes through unchanged.

## Geometry (`key.py`)

Approach A: `Text → extrude → intersect`, flat-bottomed cutter.

### `_legend_cutter() -> Part | None` (cached)

- Returns `None` when `legends` is empty.
- Reference plane above the top: `z_ref = self.max_height` (already above the
  highest corner, ~6.28mm for G20).
- For each legend: build a `Text(text, font_size=size, font=<auto|font>)`,
  centered, translated by `(dx, dy)` on the plane.
- Union all `Text` sketches, then extrude a vertical prism from above the top
  (`z_ref + margin`) down to a flat bottom at `z_floor = h_center - legend_depth`,
  where `h_center` is the top-surface height at the key center (~6.0mm for G20).
  This is the **flat-bottomed** cutter. On the near-flat G20 top (2.5° tilt, no
  dish) the resulting recess is ~uniform 0.8mm deep.

### `shape() -> Part` (material 1)

- Builds the cap exactly as today (shell + top filler + stem + inner fillet +
  optional bump).
- If a cutter exists: `body = body - cutter` (carves the recess). Otherwise
  unchanged — `default`/`redox`/`visualize.py` see no difference.

### `legend_plug() -> Part | None` (material 2)

- `plug = cutter & self._outer_key_profile()` — letter shards whose **top follows
  the cap surface exactly** (single intersection, no slivers), sharing the
  cutter's flat bottom at `z_floor`.
- Same coordinate system as the body → aligned for the slicer.

Invariant: `body + plug` reconstructs the original smooth cap. The 0.8mm recess
sits within the solid top-fill block (~1.9mm of solid below the top surface at
center), so the pocket floor and plug rest on solid material.

The cutter is built once (cached) and used by both `shape()` and `legend_plug()`.

## Export (`main.py`)

Factor the existing (already-fixed) export block into a local
`export(shape, path)` helper (module-level `export_stl/step/brep` + `Mesher` for
3mf). Then per key:

```python
body = key.shape()
plug = key.legend_plug()          # None if no legends

export(body, f"{key_name}.{fmt}")             # material 1
if plug is not None:
    export(plug, f"{key_name}.legend.{fmt}")  # material 2
```

- Naming: `q.stl` + `q.legend.stl`. Legend-free keys produce one file, as today.

## Layout

New `configs/layouts/planck_poc.yaml` with the five POC keys above. `planck.yaml`
stays as the geometry-only proof (1u + 2u); it later becomes the full legend set.

## Verification

Render `planck_poc` to STL, then preview each key in OpenSCAD (body + legend STL
together, two colours) to confirm legends are flush, crisp, and correctly
positioned. Tune dual `dy`, legend sizes, and depth against the render — the same
render-and-inspect loop used for the G20 profile. Confirm:

- `space2u` produces exactly one file (no plug).
- `body + plug` visually recomposes the smooth cap per key.
- Glyph key `tab` renders a real `⇥` (Adwaita), not tofu.

## Non-goals

- Full 48-key Planck legend map (follow-up).
- Front-printed / side legends (KeyV2 `$front_legends`).
- Raised/outset legends.
- Single-material painted-recess workflow.
