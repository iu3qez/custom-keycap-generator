# Custom Keycap Generator

> Work in progress. Contributions welcome!
> 
> Intended to fit Cherry MX switches, but compatibility is not guaranteed.

Easily generate custom keycap sets for 3d-printing.
This is primarily intended for strange key layouts, such as ergonomic or split keyboards, where pre-made keycap sets are hard to find.

> **This fork** adds per-key **legends** and a full **Planck 40% set in a uniform G20 profile**,
> built for **multi-material (MMU)** printing. Legends are flush plugs (a clean
> `Text → extrude → intersect`, no coplanar slivers) exported as a separate body, plus a stem
> support-blocker modifier per key. See [Legends & MMU](#legends--mmu-this-fork).
>
> ```bash
> uv run python main.py g20 planck -f 3mf   # full Planck G20 set, one multi-object 3mf per key
> ```

![Example keycap (stl)](img/r1.stl)
![Example keycaps (render, front)](img/render_front.png)
![Example keycaps (render, back)](img/render_back.png)
![Example keycap (drawing)](img/drawing.svg)

## Dependencies
Requires Python 3.11.
Slightly older versions may work but have not been tested.

Python dependencies:
- [build123d](https://github.com/gumyr/build123d)
- NumPy
- PyYaml
- tqdm

## Usage

Run `python main.py -h` for usage.

```bash
python main.py [style] [layout] -o [output-path] -f [format]
```

Example command to generate a set of keys in `stl` format:

```bash
python main.py default redox
```

Supported formats are inherited from `build123d`:
- stl
- brep
- step
- 3mf

This fork uses [uv](https://docs.astral.sh/uv/) (`uv sync`, then `uv run python main.py …`).

## Legends & MMU (this fork)

Keys can carry per-key legends, exported as a separate flush body for multi-material printing:

- **`<key>.<fmt>`** — the keycap body, with the legend recess carved in (material 1).
- **`<key>.legend.<fmt>`** — a flush legend plug whose top follows the cap surface (material 2);
  emitted only for keys that have legends.
- **`<key>.stem.<fmt>`** — a cylinder filling the Cherry stem's inner cross, to load in the slicer
  as a **modifier volume with supports disabled** (keeps supports out of the stem). Not printed.

In `-f 3mf` mode these are bundled into **one multi-object `<key>.3mf`** (named objects); in
stl/step/brep they are separate, coordinate-aligned files.

To get the **whole set as one file** (a CAD preview/archive), `assemble.py` lays every key out at
its grid position and writes a single multi-solid STEP:

```bash
uv run python assemble.py g20 planck   # -> output/planck.step (all keys, named solids)
```

Legends are set per key in the layout YAML:

```yaml
keys:
  q:         {base: G20, width: 1.0, legends: [{text: "Q"}]}
  esc:       {base: G20, width: 1.0, legends: [{text: "Esc", size: 3.5}]}   # word
  semicolon: {base: G20, width: 1.0, legends: [{text: ";", size: 4.0, dy: -1.2},  # stacked ANSI pair
                                               {text: ":", size: 4.0, dy:  1.2}]}
  tab:       {base: G20, width: 1.0, legends: [{text: "⇥"}]}                 # glyph
```

Each legend entry is **either** `text` **or** `svg` (a path to an SVG file, filled and carved just
like text), plus `size` (mm — cap-height for text, larger-bbox for SVG), `dx`/`dy` (offset on the
top, mm), and `font` (optional text override). Fonts are auto-selected — **Nimbus Sans** for
text/arrows, **Adwaita Sans** for the keyboard glyphs `⇥ ⌫ ⏎ ⇧`. The full example is
`configs/layouts/planck.yaml` (Planck 40%, G20, 46 keys); `configs/styles/g20.yaml` is the uniform
low profile.

## From a Vial keymap (this fork)

Generate a whole set straight from a **Vial** keymap, with up to four layers laid out in the cap's
four quadrants:

```bash
uv run python generate_vial.py g20 board.json keymap.vil -f 3mf
```

- **`board.json`** — the keyboard's Vial definition (KLE physical layout under `layouts.keymap`);
  supplies key positions and widths.
- **`keymap.vil`** — a Vial keymap export (`layout[layer][row][col]` of keycodes).

Each cap gets one legend per layer, placed clockwise from the large main legend:

| quadrant     | layer | size  |
|--------------|-------|-------|
| top-left     | 0     | large |
| top-right    | 1     | small |
| bottom-right | 2     | small |
| bottom-left  | 3     | small |

Keycodes resolve to legends automatically (`vial.py`):

- **A-Z / 0-9** and typographic symbols (`; , . / - = [ ] ! @ …`) → **text**.
- **Functional keys** (Shift, Ctrl, Alt, Cmd, Enter, Tab, Backspace, arrows, media, …) →
  **[Lucide](https://lucide.dev/icons/) icons**, fetched on demand and cached in
  `assets/lucide-cache/` (never vendored). Extend the `KEYCODE_TO_LUCIDE` map in `vial.py` to add
  more, or edit the size/offset defaults in `QuadrantSpec`.
- **Transparent/`KC_NO`** layers → that quadrant is left empty. Layer-tap / mod-tap / modifier
  wrappers show the underlying tap key; `MO(n)` etc. show `Ln`.

Add `--emit-layout out.yaml` to also dump the computed per-key legends as a layout YAML you can
hand-tune and feed back through `main.py`. Output bodies are exactly the same three per key
(`<key>` / `<key>.legend` / `<key>.stem`) as above.

## Configuration

Keycap configuration is done via two `yaml` files: a "style" (located in `configs/styles`), and a "layout" (located in `configs/layouts`).

- The "style" configuration is used to describe a family of keycaps, independent of key layout.
- The "layout" configuration takes a style and defines a specific set of keys with it.

This system is meant to be as flexible as possible.
In a simple case, the style defines the slope angles, roundness, height, etc. of the keys in each row.
It might provide some special modifiers like "convex", "concave", or "flat".
Then, the layout describes the key widths that are required for each row.
It can use the modifiers to asks for special keys, such as a convex space bar.
Additionally, it can ignore the style entirely, and manually override the properties of any keys

> See the `configs` folder for configuration examples.

The styles configuration consists of three lists:
- `global`: These options are automatically inherited by all keys.
- `bases`: Every key can choose one of these as a base configuration.
- `modifiers`: Each key can additionally list any number of modifiers to inherit.

The layout configuration consists of a list of keys.
Each can define (all optional):
- `base`: The chosen base configuration.
- `modifiers`: A list of any number of modifiers to inherit.
- Any additional options.

Three stem styles are provided:
- `formal`: Standard Cherry MX profile
<img src="img/stem_formal.png" width="200px" />
- `reinforced`: Adds extra material to the standard profile, for more strength
<img src="img/stem_reinforced.png" width="200px" />
- `minimal`: (not recommended) Minimalist stem, originally designed for a low-quality 3D printer to avoid thin walls
<img src="img/stem_minimal.png" width="200px" />

The default style `configs/styles/default.yaml` describes all available options.
