"""Assemble a whole layout into ONE multi-solid STEP file.

Places every key at its grid position (from the layout's `grid:` section) and
writes a single STEP holding all bodies + legend plugs + stem guards as named
solids — handy as a CAD preview/archive of the full set. This is separate from
main.py, which exports one printable file (or 3mf) per key.

    uv run python assemble.py g20 planck            # -> output/planck.step
    uv run python assemble.py g20 planck -o build   # -> build/planck.step
"""
from build123d import *
from build123d import export_step
import argparse
import os
import yaml
from tqdm import tqdm
from key import KeyConfig, Key
from stem import stem_from_config

UNIT = 19.0  # mm per key unit (a 1u cap is 18mm, so ~1mm gaps in the assembly)

parser = argparse.ArgumentParser("assemble", "Assemble a layout into one STEP")
parser.add_argument('style')
parser.add_argument('layout')
parser.add_argument('-o', '--output-path', default="output")


def build_key(style, key_conf):
    """Merge style+key config exactly like main.py and return a Key."""
    conf = dict(key_conf)
    base = conf.pop('base', '')
    modifiers = conf.pop('modifiers', [])
    conf.pop('pos', None)
    config = style['global'] | style['bases'].get(base, {}) | conf
    for mod in modifiers:
        config = config | style['modifiers'][mod]
    stem = stem_from_config(**config.pop('stem', {}))
    return Key(KeyConfig(**config), stem)


if __name__ == '__main__':
    args = parser.parse_args()

    with open(f"configs/styles/{args.style}.yaml") as f:
        style = yaml.safe_load(f)
    with open(f"configs/layouts/{args.layout}.yaml") as f:
        layout = yaml.safe_load(f)

    if 'grid' not in layout:
        raise SystemExit(f"layout '{args.layout}' has no `grid:` section to assemble")

    keys = layout['keys']

    # Build each distinct key's geometry once (a name may repeat in the grid).
    cache = {}
    def geometry(name):
        if name not in cache:
            k = build_key(style, keys[name])
            cache[name] = (k.shape(), k.legend_plug(), k.stem_guard())
        return cache[name]

    print(f"Assembling {args.layout}...")
    solids = []
    for r, row in enumerate(tqdm(layout['grid'])):
        cursor = 0.0
        for name in row:
            if not name:                       # blank slot
                cursor += 1.0
                continue
            width = float(keys[name].get('width', 1.0))
            loc = Location(((cursor + width / 2) * UNIT, -r * UNIT, 0))
            body, plug, guard = geometry(name)

            b = body.moved(loc); b.label = name; solids.append(b)
            if plug is not None:
                p = plug.moved(loc); p.label = f"{name}.legend"; solids.append(p)
            g = guard.moved(loc); g.label = f"{name}.stem"; solids.append(g)
            cursor += width

    assembly = Compound(children=solids, label=args.layout)
    out_path = os.path.join(args.output_path, f"{args.layout}.step")
    print(f"Writing {len(solids)} solids -> {out_path}")
    export_step(assembly, out_path)
