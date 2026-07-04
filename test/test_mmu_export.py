import os, sys, subprocess, tempfile

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _render(outdir):
    r = subprocess.run(
        ["uv", "run", "python", "main.py", "g20", "planck_poc", "-o", outdir],
        cwd=_HERE, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return outdir

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

if __name__ == "__main__":
    test_legended_key_has_two_files(); print("OK legended key -> 2 files")
    test_blank_key_has_one_file(); print("OK blank key -> 1 file")
