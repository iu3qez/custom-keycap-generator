import os, re, subprocess, tempfile, zipfile

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _render(outdir, fmt="stl"):
    r = subprocess.run(
        ["uv", "run", "python", "main.py", "g20", "planck_poc", "-o", outdir, "-f", fmt],
        cwd=_HERE, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return outdir

def _obj_names(path):
    """The set of object names (part numbers) inside a 3mf archive."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("3D/3dmodel.model").decode("utf-8", "replace")
    return set(re.findall(r'(?:name|partnumber)="([^"]*)"', xml, re.I))

def test_legended_key_has_two_files():
    with tempfile.TemporaryDirectory() as d:
        _render(d)
        assert os.path.exists(os.path.join(d, "q.stl"))
        assert os.path.exists(os.path.join(d, "q.legend.stl"))

def test_blank_key_has_one_file():
    with tempfile.TemporaryDirectory() as d:
        _render(d)
        assert os.path.exists(os.path.join(d, "space2u.stl"))
        assert not os.path.exists(os.path.join(d, "space2u.legend.stl"))

def test_every_key_has_a_stem_modifier():
    # the stem support-blocker is emitted for every key (legended or not)
    with tempfile.TemporaryDirectory() as d:
        _render(d)
        assert os.path.exists(os.path.join(d, "q.stem.stl"))
        assert os.path.exists(os.path.join(d, "space2u.stem.stl"))

def test_3mf_bundles_objects_per_key():
    # 3mf mode packs a key's body + legend + stem into ONE multi-object file
    with tempfile.TemporaryDirectory() as d:
        _render(d, fmt="3mf")
        q = _obj_names(os.path.join(d, "q.3mf"))
        assert {"q", "q.legend", "q.stem"} <= q
        sp = _obj_names(os.path.join(d, "space2u.3mf"))
        assert "space2u" in sp and "space2u.stem" in sp
        assert not any("legend" in n for n in sp)   # blank key -> no legend object

if __name__ == "__main__":
    test_legended_key_has_two_files(); print("OK legended key -> 2 files")
    test_blank_key_has_one_file(); print("OK blank key -> 1 file")
    test_every_key_has_a_stem_modifier(); print("OK stem modifier per key")
    test_3mf_bundles_objects_per_key(); print("OK 3mf multi-object bundle")
