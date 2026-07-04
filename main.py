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

        def export_shape(shape, path):
            if args.format == 'stl':
                export_stl(shape, path)
            elif args.format == 'brep':
                export_brep(shape, path)
            elif args.format == 'step':
                export_step(shape, path)
            elif args.format == '3mf':
                mesher = Mesher(unit=Unit.MM)
                mesher.add_shape(shape, linear_deflection=1e-3, angular_deflection=0.1)
                mesher.write(path)

        base_path = os.path.join(args.output_path, f"{key_name}.{args.format}")
        export_shape(key.shape(), base_path)                 # material 1

        plug = key.legend_plug()
        if plug is not None:                                  # material 2
            plug_path = os.path.join(
                args.output_path, f"{key_name}.legend.{args.format}"
            )
            export_shape(plug, plug_path)

        # Slicer support-blocker modifier (fills the stem's inner cross)
        stem_path = os.path.join(
            args.output_path, f"{key_name}.stem.{args.format}"
        )
        export_shape(key.stem_guard(), stem_path)
