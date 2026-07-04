"""Shared builders for the plain-assert legend test scripts."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from key import KeyConfig, Key
from stem import stem_from_config

# G20 reference geometry (mirrors configs/styles/g20.yaml)
_G20 = dict(
    tol=0.1, tol_tight=0.1, wall=1.2, inner_rad=0.3,
    key_h=18.0, key_r=1.75,
    back_slope=9.5, front_slope=9.5, side_slope=9.5,
    back_curve=0.0, front_curve=0.0,
    back_dy=6.35, front_dy=5.65, width=1.0,
)

def make_key(legends=None, **overrides):
    cfg = dict(_G20)
    cfg.update(overrides)
    if legends is not None:
        cfg["legends"] = legends
    return Key(KeyConfig(**cfg), stem_from_config(type="formal"))

import yaml

def build_from_layout(layout_name, style_name="g20"):
    """Merge style+layout exactly like main.py and return {key_name: Key}."""
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(_here, f"configs/styles/{style_name}.yaml")) as f:
        style = yaml.safe_load(f)
    with open(os.path.join(_here, f"configs/layouts/{layout_name}.yaml")) as f:
        layout = yaml.safe_load(f)

    keys = {}
    for name, kc in layout["keys"].items():
        base = kc.pop("base", "")
        mods = kc.pop("modifiers", [])
        cfg = style["global"] | style["bases"].get(base, {}) | kc
        for m in mods:
            cfg = cfg | style["modifiers"][m]
        stem = stem_from_config(**cfg.pop("stem", {}))
        keys[name] = Key(KeyConfig(**cfg), stem)
    return keys
