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

        out_path = os.path.join(args.output_path, f"{key_name}.{args.format}")
        shape = key.shape()
        if args.format == 'stl':
            export_stl(shape, out_path)
        elif args.format == 'brep':
            export_brep(shape, out_path)
        elif args.format == 'step':
            export_step(shape, out_path)
        elif args.format == '3mf':
            mesher = Mesher(unit=Unit.MM)
            mesher.add_shape(shape, linear_deflection=1e-3, angular_deflection=0.1)
            mesher.write(out_path)
