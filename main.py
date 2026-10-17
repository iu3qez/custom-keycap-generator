from build123d import *
from build123d import export_stl, export_step, export_brep, Mesher
import argparse
import os
import yaml
from tqdm import tqdm
from assemble import UNIT
from key import KeyConfig, Key
from orca3mf import export_orca_3mf, board_to_plate
from stem import stem_from_config
from vial import resolve_icon_legends

parser = argparse.ArgumentParser(
    "Custom Keycap Generator",
    "Generate custom print-ready keycap geometries",
    "Work in progress. Contributions welcome."
)
parser.add_argument('style')
parser.add_argument('layout')
parser.add_argument('-o', '--output-path', default="output")
parser.add_argument('-f', '--format', default='stl', choices=['stl', 'brep', 'step', '3mf'])
parser.add_argument('--orca', action='store_true',
                    help="also write the whole set as one OrcaSlicer-ready 3mf "
                         "(<layout>.orca.3mf); every key needs `pos`")
parser.add_argument('--step', action='store_true',
                    help="also write the whole set as one multi-solid STEP "
                         "(<layout>.step); every key needs `pos`")

if __name__ == '__main__':
    args = parser.parse_args()

    with open(f"configs/styles/{args.style}.yaml") as f:
        style = yaml.safe_load(f.read())
    with open(f"configs/layouts/{args.layout}.yaml") as f:
        layout = yaml.safe_load(f)

    def export_shape(shape, path):
        if args.format == 'stl':
            export_stl(shape, path)
        elif args.format == 'brep':
            export_brep(shape, path)
        elif args.format == 'step':
            export_step(shape, path)

    def export_3mf_multi(parts, path):
        # One 3mf holding several named, aligned objects (body / legend / stem),
        # ideal for MMU: import one file, then assign a material or modifier per
        # object in the slicer. `parts` is a list of (object_name, shape).
        mesher = Mesher(unit=Unit.MM)
        for name, shape in parts:
            mesher.add_shape(
                shape, linear_deflection=1e-3, angular_deflection=0.1,
                part_number=name,
            )
        mesher.write(path)

    if args.orca or args.step:
        missing = [n for n, kc in layout['keys'].items() if 'pos' not in kc]
        if missing:
            parser.error(f"--orca/--step need `pos` on every key; missing on "
                         f"{', '.join(missing[:5])}{' ...' if len(missing) > 5 else ''}")
    os.makedirs(args.output_path, exist_ok=True)

    solids = []
    orca_keys = []
    print(f"Generating {len(layout['keys'])} keys...")
    for key_name, key_conf in tqdm(layout['keys'].items()):
        base = key_conf.pop('base', '')
        modifiers = key_conf.pop('modifiers', [])
        pos = key_conf.pop('pos', None)     # key top-left, in units
        if 'legends' in key_conf:
            key_conf['legends'] = resolve_icon_legends(key_conf['legends'])
        config = (
                style['global'] |
                style['bases'].get(base, {}) |
                key_conf
        )
        for mod in modifiers:
            config = config | style['modifiers'][mod]
        stem = stem_from_config(**config.pop('stem', {}))
        key_config = KeyConfig(**config)
        key = Key(key_config, stem)

        body = key.shape()               # material 1 (keycap with the recess)
        plug = key.legend_plug()         # material 2 (flush legend, None if bare)
        guard = key.stem_guard()         # slicer support-blocker modifier

        if args.format == '3mf':
            # Bundle every body of a key into ONE multi-object 3mf.
            parts = [(key_name, body)]
            if plug is not None:
                parts.append((f"{key_name}.legend", plug))
            parts.append((f"{key_name}.stem", guard))
            export_3mf_multi(parts, os.path.join(args.output_path, f"{key_name}.3mf"))
        else:
            out = args.output_path
            fmt = args.format
            export_shape(body, os.path.join(out, f"{key_name}.{fmt}"))
            if plug is not None:
                export_shape(plug, os.path.join(out, f"{key_name}.legend.{fmt}"))
            export_shape(guard, os.path.join(out, f"{key_name}.stem.{fmt}"))

        if pos is not None:
            # key center in board mm (y grows downwards, as in KLE)
            cx = (pos[0] + config['width'] / 2) * UNIT
            cy = (pos[1] + 0.5) * UNIT
            if args.step:
                loc = Location((cx, -cy, 0))
                for label, part in ((key_name, body), (f"{key_name}.legend", plug),
                                    (f"{key_name}.stem", guard)):
                    if part is not None:
                        moved = part.moved(loc)
                        moved.label = label
                        solids.append(moved)
            if args.orca:
                orca_keys.append((key_name, (cx, cy),
                                  {"body": body, "legend": plug, "stem": guard}))

    if args.step:
        step_path = os.path.join(args.output_path, f"{args.layout}.step")
        export_step(Compound(children=solids, label=args.layout), step_path)
        print(f"Wrote {len(solids)} solids -> {step_path}")
    if args.orca:
        orca_path = os.path.join(args.output_path, f"{args.layout}.orca.3mf")
        export_orca_3mf(board_to_plate(orca_keys), orca_path)
        print(f"Wrote {len(orca_keys)} keys -> {orca_path}")
