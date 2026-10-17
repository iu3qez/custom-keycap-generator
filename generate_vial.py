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
from build123d import Compound, Location
from tqdm import tqdm

from assemble import UNIT
from orca3mf import export_orca_3mf, board_to_plate
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
                    help="also write the computed keys as a layout YAML "
                         "(editable; build it with main.py)")
parser.add_argument("--layout-only", action="store_true",
                    help="with --emit-layout: write the YAML and build no caps")
parser.add_argument("--step", action="store_true",
                    help="also write the whole set as one multi-solid STEP "
                         "(<keymap>.step), each cap at its board position")
parser.add_argument("--legend-depth", type=float, default=None,
                    help="legend recess depth in mm (default: style value, "
                         "0.8); ~1.8 on G20 reaches the cavity ceiling")
parser.add_argument("--orca", action="store_true",
                    help="also write the whole set as one OrcaSlicer-ready 3mf "
                         "(<keymap>.orca.3mf): one object per key, legend on "
                         "filament 2, stem as support blocker")


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


def _rounded(legends: list[dict]) -> list[dict]:
    """Legends with floats rounded to 0.01 mm, for a readable YAML."""
    first = ("text", "icon", "svg")
    out = []
    for leg in legends:
        items = sorted(leg.items(), key=lambda kv: kv[0] not in first)
        out.append({k: round(v, 2) if isinstance(v, float) else v for k, v in items})
    return out


def write_layout(path: str, keymap: str, keys: dict) -> None:
    with open(path, "w") as f:
        f.write(f"# Generated from {os.path.basename(keymap)} by generate_vial.py "
                "--emit-layout.\n"
                "# pos = key top-left in units (1u = 19 mm), width in units.\n"
                "# icon = Lucide icon name; build with: "
                "uv run python main.py <style> <layout> [--orca] [--step]\n")
        yaml.safe_dump({"keys": keys}, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=None, width=100)
    print(f"Wrote computed layout -> {path}")


def main():
    args = parser.parse_args()
    if args.layout_only and not args.emit_layout:
        parser.error("--layout-only needs --emit-layout PATH")
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
    solids = []
    orca_keys = []
    if args.emit_layout:
        # Icons by Lucide name (fetch=False), so the YAML is easy to edit.
        for pk in keys:
            kcs = keycodes_for(layout, pk, layers)
            legs = quadrant_legends(kcs, key_h * pk.w, key_h, spec, fetch=False)
            emitted[pk.name] = {"base": args.base, "width": pk.w,
                                "pos": [pk.x, pk.y], "legends": _rounded(legs)}
        write_layout(args.emit_layout, args.keymap, emitted)
        if args.layout_only:
            return

    for pk in tqdm(keys):
        kcs = keycodes_for(layout, pk, layers)
        key_w = key_h * pk.w
        legends = quadrant_legends(kcs, key_w, key_h, spec, args.glyph_dir)

        conf = (
            dict(style["global"])
            | style.get("bases", {}).get(args.base, {})
            | {"width": pk.w, "legends": legends}
        )
        if args.legend_depth is not None:
            conf["legend_depth"] = args.legend_depth
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

        if args.step:
            loc = Location(((pk.x + pk.w / 2) * UNIT, -(pk.y + pk.h / 2) * UNIT, 0))
            for label, part in ((name, body), (f"{name}.legend", plug),
                                (f"{name}.stem", guard)):
                if part is not None:
                    moved = part.moved(loc)
                    moved.label = label
                    solids.append(moved)

        if args.orca:
            orca_keys.append((name, ((pk.x + pk.w / 2) * UNIT, (pk.y + pk.h / 2) * UNIT),
                              {"body": body, "legend": plug, "stem": guard}))

    if args.step:
        set_name = os.path.splitext(os.path.basename(args.keymap))[0]
        step_path = os.path.join(args.output_path, f"{set_name}.step")
        export_step(Compound(children=solids, label=set_name), step_path)
        print(f"Wrote {len(solids)} solids -> {step_path}")

    if args.orca:
        orca_keys = board_to_plate(orca_keys)
        set_name = os.path.splitext(os.path.basename(args.keymap))[0]
        orca_path = os.path.join(args.output_path, f"{set_name}.orca.3mf")
        export_orca_3mf(orca_keys, orca_path)
        print(f"Wrote {len(orca_keys)} keys -> {orca_path}")


if __name__ == "__main__":
    main()
