from _helpers import build_from_layout

def test_poc_keys_present():
    keys = build_from_layout("planck_poc")
    assert set(keys) == {"q", "esc", "semicolon", "tab", "space2u"}

def test_every_key_builds():
    keys = build_from_layout("planck_poc")
    for name, k in keys.items():
        assert k.shape().volume > 0, name

def test_plug_presence():
    keys = build_from_layout("planck_poc")
    assert keys["q"].legend_plug() is not None
    assert keys["esc"].legend_plug() is not None
    assert keys["semicolon"].legend_plug() is not None
    assert keys["tab"].legend_plug() is not None
    assert keys["space2u"].legend_plug() is None      # blank 2u -> no plug

def test_dual_legend_has_more_volume_than_single():
    # the stacked ; : plug must carve more than a single-char ; plug
    from _helpers import make_key
    keys = build_from_layout("planck_poc")
    dual_v = keys["semicolon"].legend_plug().volume
    single_v = make_key(legends=[{"text": ";", "size": 4.0}]).legend_plug().volume
    assert dual_v > single_v

if __name__ == "__main__":
    test_poc_keys_present(); print("OK poc keys present")
    test_every_key_builds(); print("OK every key builds")
    test_plug_presence(); print("OK plug presence")
    test_dual_legend_has_more_volume_than_single(); print("OK dual legend")
