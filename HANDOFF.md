# Handoff — Planck G20 keycaps (2026-07-03)

Session close. Where things stand and what to do next.

## The story so far

Goal: a full **Planck 40% keycap set, G20 uniform profile, per-key legends, 2u spacebar**,
printable in multi-material (MMU: keycap body + separate flush legend body).

We built this first in **OpenSCAD/KeyV2** (`../KeyV2/planck_g20.scad`), then hit a wall and
decided to **port to build123d** (this repo). uv env is set up and working.

### Done in `../KeyV2` (committed on branch `claude/openscad-env-check-vyjqlo`)

- `6cd5716` fix: disable tines stem-support in the G20 flush example
  (`examples/g20_flush_multimaterial_legend.scad`). Correct token is `$stem_support_type="disable"`
  (not `"disabled"`). `flared` support produces ~nothing on a low profile like G20 (no vertical room).
- `ac8ccf6` feat: `planck_g20.scad` — full Planck set, G20, gap-aware 13-col legends, 2u space.
- `f8cd781` feat: stacked dual legends on punctuation (`;: ,< .> /?`), per-key legend sizing,
  hybrid **Nimbus Sans** (text) + **DejaVu** (keyboard glyphs `⇥ ⌫ ⏎ ⇧`) fonts.

### Why we're leaving OpenSCAD

The flush **multimaterial legend plugs are broken meshes**. `models/planck_legends.3mf` (and the
render) show thin triangular **sliver shards** radiating from every letter. Root cause: the plug
is `difference(smooth_cap, recessed_cap)`; the two caps' **dished top surfaces are coincident but
triangulated differently**, so the boolean leaves coplanar slivers. It is "manifold" (export
shows NoError) but visually ruined in the slicer. Doing the difference per-key did **not** fix it
(same cause at single-key scale). CGAL backend export timed out (>2 min). This class of
coplanar-boolean fragility is exactly why we're switching to a B-rep kernel.

> The `../KeyV2/planck_g20.scad` **keys** part (bodies with recessed legends) renders fine — only
> the separate **legends** plug body is the problem. Nimbus/DejaVu font choice and the layout are good.

## This repo (build123d fork) — current state

- Forked `nicola-sorace/custom-keycap-generator` → **`iu3qez/custom-keycap-generator`**, cloned to
  `/home/sf/src/custom-keycap-generator`.
- Added `pyproject.toml`; **`uv sync` done**, `uv run python -c "import build123d"` works
  (build123d 0.11.1, Python 3.11). `.venv` present.
- Added `CLAUDE.md` (architecture + how to reach the G20 goal). **Nothing committed yet** in this
  repo — `pyproject.toml`, `CLAUDE.md`, `HANDOFF.md` are uncommitted new files.

Read `CLAUDE.md` here first — it explains the 3-file pipeline (`main.py`/`key.py`/`stem.py`),
how "profiles" are just per-row `back_dy/front_dy`, and that **upstream has no legend support**.

## Next steps (in order)

1. **Commit the scaffolding** in this repo (`pyproject.toml`, `CLAUDE.md`, `HANDOFF.md`).
2. **G20 style + Planck layout YAML** (no legends yet): `configs/styles/g20.yaml` with one uniform
   flat base (`back_dy == front_dy`, low; near-zero slopes/curves), `stem: {type: formal}`. A
   `configs/layouts/planck.yaml` really only needs **one 1u + one 2u** key (uniform → all 1u
   identical). Verify with `uv run python main.py g20 planck -f 3mf`.
3. **Add legends to `key.py`** (the real work): `Text(...) → extrude → intersect(cap)` for a clean
   flush plug; return the plug as a **separate body** for MMU. Reuse the KeyV2 decisions: dual
   ANSI legends on punctuation, hybrid Nimbus/DejaVu fonts, gap-aware Planck legend map.
4. Wire per-key legend text through the layout YAML, regenerate the full set, slice to confirm the
   legend body is clean (the thing OpenSCAD couldn't do).

## Env / infra notes

- OpenSCAD here is the **2026.06.12 dev snapshot** at `/usr/bin/openscad` (Manifold backend
  default; fast STL export, no GL needed). `xvfb-run` is **gone**, but `DISPLAY=:1` is live, so
  PNG previews and the OpenSCAD GUI work directly (`DISPLAY=:1 openscad file.scad`).
- Global user pref: **git commits must not include Co-Authored-By lines**.
