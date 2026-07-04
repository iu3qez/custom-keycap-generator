# Handoff — Planck G20 keycaps (updated 2026-07-04)

Status of the build123d fork. The original goal is **done**; this file records where things
landed and what's optional next.

## Goal (achieved)

A full **Planck 40% (4×12 ortholinear, MIT 2u spacebar) keycap set in a uniform G20 profile with
per-key legends**, printable multi-material (MMU): keycap body + separate flush legend body +
per-key stem support-blocker. All on `main`, pushed to `iu3qez/custom-keycap-generator`.

## What's implemented

- **G20 profile** — `configs/styles/g20.yaml`: uniform low base, flat top, 1.75mm edges, ~9.5°
  taper, 2.5° micro-tilt (`back_dy 6.35 / front_dy 5.65`), `inner_rad 0.3`, `formal` stem. Ported
  from `../KeyV2/src/key_profiles/g20.scad`.
- **Legend engine** — `key.py`: `_legend_cutter` (`Text → extrude`, flat floor 0.8mm below the
  top-center), `shape()` subtracts it (recess), `legend_plug()` = `cutter & _outer_key_profile()`
  (flush plug, single intersection → no coplanar slivers; `body + plug` ≈ smooth cap to ~0.008mm³).
  Hybrid fonts via `_legend_font_for`: Nimbus Sans for text/arrows, Adwaita Sans for `⇥ ⌫ ⏎ ⇧`
  (DejaVu from KeyV2 isn't installed here).
- **Stem guard** — `key.py: stem_guard()`: a cylinder (radius = Cherry tube `stem.stem_rad`,
  height `stem_depth`, from z=0) that fills the stem's inner cross; load as a slicer no-support
  modifier. Exported per key.
- **Full set** — `configs/layouts/planck.yaml`: 46 distinct keys (shift shared by both row-2
  corners), ANSI dual pairs on `; , . /`, words on `Esc/Ctl/Alt/Cmd/Lwr/Rse/Fn`, glyphs, arrows,
  2u blank spacebar. `configs/layouts/planck_poc.yaml` is the 5-key proof-of-concept.
- **MMU export** — `main.py`: per key writes `<key>.<fmt>` (body), `<key>.legend.<fmt>` (if any),
  `<key>.stem.<fmt>`. In `-f 3mf`, bundles them into one **multi-object `<key>.3mf`** (named
  objects). Uses build123d **module-level** exporters + `Mesher` (the older `.export_*()` method
  calls were broken and were fixed).
- **Exporter fix** — `main.py` originally called `Part.export_stl()` etc., which don't exist in
  build123d 0.11.1; now uses `export_stl/step/brep` + `Mesher`.

## Build & test

```bash
uv sync
uv run python main.py g20 planck            # full set -> output/ (STL)   (~2 min, 46 keys)
uv run python main.py g20 planck -f 3mf      # one multi-object 3mf per key
uv run python main.py g20 planck_poc         # 5-key proof-of-concept
```

Tests are plain `assert` scripts (no pytest): `uv run python test/<file>.py`.
- `test/test_legend_fonts.py`, `test/test_legend_geometry.py`, `test/test_poc_layout.py`,
  `test/test_stem_guard.py` — fast unit checks.
- `test/test_mmu_export.py` — subprocess: renders the POC set (stl + 3mf), checks the file set and
  3mf object bundling.

Docs: `docs/superpowers/specs/2026-07-04-keycap-legends-design.md` (spec),
`docs/superpowers/plans/2026-07-04-keycap-legends.md` (plan).

## Known gaps / optional next

- **`Mesher.read()` hangs** (build123d bug) — the 3mf test inspects the archive XML instead. Read
  is only needed for verification, not for export.
- **3mf per-object color** isn't exported by `Mesher` (checked) — the slicer assigns materials by
  object/name, not auto-mapped by color.
- **Legend islands**: a legend with disconnected glyphs (e.g. "Esc") becomes several same-named
  `<key>.legend` objects in the 3mf — cosmetic, all one material.
- **Flat-floor caveat**: the legend cutter floor is flat, fine for the near-flat uniform G20 top.
  A **sculpted/non-uniform** profile or a very large legend `dy` would need a tilted floor or a
  `dy` clamp (see the `legend-flat-floor-caveat` memory).
- **Tuning**: legend sizes / dual `dy` / depth were validated by render but not against physical
  MMU prints — worth a print test.

## Related prior work

`../KeyV2` (`planck_g20.scad`, `src/key_profiles/g20.scad`) — the OpenSCAD prototype these
decisions came from. We left OpenSCAD because its flush legend plugs were broken meshes (coplanar
`difference` slivers); the build123d single-`intersect` plug fixed exactly that.
