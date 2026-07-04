from _helpers import make_key
from key import SYMBOL_GLYPHS

def test_symbol_glyph_set():
    assert SYMBOL_GLYPHS == {"⇥", "⌫", "⏎", "⇧"}

def test_font_auto_selection():
    k = make_key(legends=[])
    assert k._legend_font_for("Q") == "Nimbus Sans"     # letter -> main
    assert k._legend_font_for("←") == "Nimbus Sans"     # arrow -> main
    # every keyboard glyph routes to the symbol font
    for glyph in SYMBOL_GLYPHS:
        assert k._legend_font_for(glyph) == "Adwaita Sans", glyph

def test_font_override():
    k = make_key(legends=[])
    assert k._legend_font_for("⇥", "Custom Sans") == "Custom Sans"

def test_config_defaults():
    k = make_key(legends=[])
    assert k.legend_depth == 0.8
    assert k.legend_size == 5.5
    assert k.legend_font == "Nimbus Sans"
    assert k.legend_symbol_font == "Adwaita Sans"
    assert k.legends == []

if __name__ == "__main__":
    test_symbol_glyph_set(); print("OK symbol glyph set")
    test_font_auto_selection(); print("OK font auto-selection")
    test_font_override(); print("OK font override")
    test_config_defaults(); print("OK config defaults")
