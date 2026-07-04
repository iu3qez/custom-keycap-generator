from build123d import *
from build123d import export_stl, export_step, export_brep, Mesher
import argparse
import os
import yaml
from tqdm import tqdm
from key import KeyConfig, Key
from stem import stem_from_config

parser = argparse.ArgumentParser(
    "Custom Keycap Generator",
    "Generate custom print-ready keycap geometries",
    "Work in progress. Contributions welcome."
)
parser.add_argument('style')
parser.add_argument('layout')
parser.add_argument('-o', '--output-path', default="output")
parser.add_argument('-f', '--format', default='stl', choices=['stl', 'brep', 'step', '3mf'])

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

    print(f"Generating {len(layout['keys'])} keys...")
    for key_name, key_conf in tqdm(layout['keys'].items()):
        base = key_conf.pop('base', '')
        modifiers = key_conf.pop('modifiers', [])
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
