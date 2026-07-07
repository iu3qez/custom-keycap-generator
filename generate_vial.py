"""
Generate a keycap set from a Vial keymap.

    uv run python generate_vial.py <style> <board.json> <keymap.vil> [options]

Reads the physical layout from a Vial keyboard definition (`board.json`, KLE
format) and the per-layer keycodes from a Vial keymap export (`keymap.vil`),
then builds one cap per physical key with up to four quadrant legends (layer 0
large top-left; layers 1/2/3 small, clockwise). A-Z/0-9 are text; functional
keys are Lucide icons fetched on demand into the cache dir. See `vial.py`.

Bodies exported per key mirror `main.py`: `<key>.<fmt>` (cap, material 1),
`<key>.legend.<fmt>` (flush legend plug, material 2), `<key>.stem.<fmt>`
(support-blocker modifier). In `3mf` mode all three are bundled into one
multi-object `<key>.3mf`.
"""

import argparse
import os
import yaml
from build123d import Unit
from build123d import export_stl, export_step, export_brep, Mesher
from tqdm import tqdm

from key import KeyConfig, Key
from stem import stem_from_config
from vial import (
    parse_board, board_from_keymap, parse_keymap, keycodes_for,
    quadrant_legends, QuadrantSpec, PhysKey, DEFAULT_CACHE,
)

parser = argparse.ArgumentParser(
    "generate_vial", description="Generate a keycap set from a Vial keymap")
parser.add_argument("style", help="style name in configs/styles (e.g. g20)")
parser.add_argument("keymap", help="path to Vial keymap export (.vil)")
parser.add_argument("--board", default=None,
                    help="Vial keyboard definition (KLE json) for physical "
                         "positions/widths; omit to derive a 1u ortho grid "
                         "(with 2u gaps) straight from the keymap matrix")
parser.add_argument("-o", "--output-path", default="output")
parser.add_argument("-f", "--format", default="stl",
                    choices=["stl", "brep", "step", "3mf"])
parser.add_argument("--base", default="G20",
                    help="style base to apply to every key (default: G20)")
parser.add_argument("--layers", type=int, default=4,
                    help="number of layers to place in quadrants (max 4)")
parser.add_argument("--glyph-dir", default=DEFAULT_CACHE,
                    help="Lucide icon cache directory")
parser.add_argument("--emit-layout", metavar="PATH",
                    help="also write the computed keys as a layout YAML")


def export_shape(shape, path, fmt):
    if fmt == "stl":
        export_stl(shape, path)
    elif fmt == "brep":
        export_brep(shape, path)
    elif fmt == "step":
        export_step(shape, path)


def export_3mf_multi(parts, path):
    mesher = Mesher(unit=Unit.MM)
    for name, shape in parts:
        mesher.add_shape(shape, linear_deflection=1e-3, angular_deflection=0.1,
                         part_number=name)
    mesher.write(path)


def main():
    args = parser.parse_args()
    layers = max(1, min(4, args.layers))

    with open(f"configs/styles/{args.style}.yaml") as f:
        style = yaml.safe_load(f)
    layout = parse_keymap(args.keymap)
    if args.board:
        keys = parse_board(args.board)
        source = f"board '{os.path.basename(args.board)}'"
    else:
        keys = board_from_keymap(layout)
        source = "keymap matrix (ortho fallback)"
    print(f"{len(keys)} keys from {source}; keymap: {len(layout)} layers "
          f"(placing {layers}).")

    key_h = float(style["global"]["key_h"])
    spec = QuadrantSpec()
    os.makedirs(args.output_path, exist_ok=True)

    emitted: dict[str, dict] = {}
    for pk in tqdm(keys):
        kcs = keycodes_for(layout, pk, layers)
        key_w = key_h * pk.w
        legends = quadrant_legends(kcs, key_w, key_h, spec, args.glyph_dir)

        conf = (
            dict(style["global"])
            | style.get("bases", {}).get(args.base, {})
            | {"width": pk.w, "legends": legends}
        )
        stem = stem_from_config(**conf.pop("stem", {}))
        key = Key(KeyConfig(**conf), stem)

        body = key.shape()
        plug = key.legend_plug()
        guard = key.stem_guard()

        name = pk.name
        if args.format == "3mf":
            parts = [(name, body)]
            if plug is not None:
                parts.append((f"{name}.legend", plug))
            parts.append((f"{name}.stem", guard))
            export_3mf_multi(parts, os.path.join(args.output_path, f"{name}.3mf"))
        else:
            fmt = args.format
            out = args.output_path
            export_shape(body, os.path.join(out, f"{name}.{fmt}"), fmt)
            if plug is not None:
                export_shape(plug, os.path.join(out, f"{name}.legend.{fmt}"), fmt)
            export_shape(guard, os.path.join(out, f"{name}.stem.{fmt}"), fmt)

        if args.emit_layout:
            emitted[name] = {"base": args.base, "width": pk.w, "legends": legends}

    if args.emit_layout:
        with open(args.emit_layout, "w") as f:
            yaml.safe_dump({"keys": emitted}, f, allow_unicode=True,
                           sort_keys=False)
        print(f"Wrote computed layout -> {args.emit_layout}")


if __name__ == "__main__":
    main()
