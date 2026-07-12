from build123d import *
import numpy as np
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from stem import Stem


SYMBOL_GLYPHS = {"⇥", "⌫", "⏎", "⇧"}

# Lucide icons are stroke SVGs (fill:none, stroke-width 2 in a 24u viewbox).
# Open strokes are inflated into ribbons of this width so they become solids.
SVG_STROKE_WIDTH = 2.0


@lru_cache(maxsize=256)
def _svg_faces(path: str) -> Sketch:
    """Import an SVG into a filled, origin-centered, Y-up Sketch in the SVG's
    native units (unscaled). Faces are kept as-is; closed wires are filled;
    open strokes (Lucide) are inflated into ribbons via a both-sides offset.
    Cached by path so an icon shared across many keys is imported once."""
    objs = import_svg(path)
    sk = Sketch()
    for o in objs:
        try:
            if isinstance(o, Face):
                sk += o
            elif isinstance(o, (Wire, Edge)):
                wire = o if isinstance(o, Wire) else Wire([o])
                if getattr(wire, "is_closed", False):
                    sk += make_face(wire)
                else:
                    ribbon = offset(
                        wire, amount=SVG_STROKE_WIDTH / 2.0,
                        side=Side.BOTH, closed=False,
                    )
                    sk += make_face(ribbon)
        except Exception:
            # Skip the odd un-fillable sub-path rather than fail the whole icon.
            continue
    if not sk.faces():
        raise ValueError(f"no drawable geometry in SVG: {path}")
    # SVG space is y-down; center at origin and flip to build123d's y-up.
    center = sk.bounding_box().center()
    sk = sk.moved(Location((-center.X, -center.Y, 0)))
    return mirror(sk, about=Plane.XZ)


def svg_legend_sketch(path: str, size: float) -> Sketch:
    """A filled Sketch for an SVG legend, centered at the origin and scaled so
    its larger dimension equals `size` (mm)."""
    sk = _svg_faces(path)
    span = max(sk.bounding_box().size.X, sk.bounding_box().size.Y)
    if span > 1e-9:
        sk = scale(sk, by=size / span)
    return sk


@dataclass
class KeyConfig:
    tol: float
    tol_tight: float
    wall: float
    inner_rad: float

    key_h: float
    key_r: float

    back_slope: float
    front_slope: float
    side_slope: float
    back_curve: float
    front_curve: float

    front_dy: float
    back_dy: float
    width: float  # As a multiple of `key_h`
    bump: bool = False
    legends: list = field(default_factory=list)
    legend_depth: float = 0.8
    legend_size: float = 5.5
    legend_font: str = "Nimbus Sans"
    legend_symbol_font: str = "Adwaita Sans"
    # Backlit mode: carve the legends all the way through the opaque top layer
    # (into the cavity) instead of a blind recess, and close the holes from
    # behind with a transparent diffuser slab of `diffuser_depth` on the inner
    # ceiling. The legend plug (material 2, printed transparent) then becomes
    # diffuser + through-columns as one connected body, lit by LEDs below.
    legend_through: bool = False
    diffuser_depth: float = 0.8


class Key:
    def __init__(self, config: KeyConfig, stem: Stem):
        self.tol = config.tol
        self.tol_tight = config.tol_tight
        self.wall = config.wall

        self.key_h = config.key_h
        self.key_w = self.key_h * config.width
        self.back_dy = config.back_dy
        self.front_dy = config.front_dy

        self.back_slope = np.radians(config.back_slope)
        self.front_slope = np.radians(config.front_slope)
        self.side_slope = np.radians(config.side_slope)

        self.back_curve = config.back_curve
        self.front_curve = config.front_curve

        self.max_back_height = self.back_dy + max(0.0, -self.back_curve) + 1.0
        self.max_front_height = self.front_dy + max(0.0, -self.front_curve) + 1.0
        self.max_height = max(self.max_back_height, self.max_front_height)

        self.key_r = config.key_r
        self.inner_rad = config.inner_rad
        self.eps = 0.001

        self.cross_height = 4.1 + self.tol
        self.cross_thick = 1.17 + self.tol_tight
        self.stem_depth = 3.8 + self.tol
        self.stem_rad = 0.3

        self.bump = config.bump
        self.legends = config.legends
        self.legend_depth = config.legend_depth
        self.legend_size = config.legend_size
        self.legend_font = config.legend_font
        self.legend_symbol_font = config.legend_symbol_font
        self.legend_through = config.legend_through
        self.diffuser_depth = config.diffuser_depth

        self.stem = stem

    def _legend_font_for(self, text: str, override: str | None = None) -> str:
        """Pick the font for a legend: explicit override, else the symbol font
        for keyboard glyphs, else the main font."""
        if override:
            return override
        if any(ch in SYMBOL_GLYPHS for ch in text):
            return self.legend_symbol_font
        return self.legend_font

    @cached_property
    def _legend_cutter(self) -> "Part | None":
        """Vertical prism of the legend glyphs, flat-bottomed at `z_floor`,
        tall enough to pass above the cap top. Subtracting it carves the recess;
        intersecting it with the outer profile yields the flush plug."""
        if not self.legends:
            return None

        # In backlit mode the glyphs are through-holes: the floor drops to the
        # top of the diffuser slab (the inner ceiling raised by `diffuser_depth`)
        # so the cut passes entirely through the opaque top layer. Otherwise the
        # flat floor sits `legend_depth` below the center top (a blind recess).
        if self.legend_through:
            # Sink the floor into the diffuser top by a real overlap (not just
            # `eps`) so the through-columns and the diffuser slab reliably fuse
            # into one connected plug solid.
            overlap = min(0.2, self.diffuser_depth / 2.0)
            z_floor = self._top_inner_z + self.diffuser_depth - overlap
        else:
            # Top-surface height at the key center (recess depth ~uniform on the
            # near-flat top).
            h_center = (self.front_dy + self.back_dy) / 2.0
            z_floor = h_center - self.legend_depth
        z_top = self.max_height + 1.0            # safely above the tallest corner

        with BuildPart() as cutter:
            with BuildSketch(Plane.XY.offset(z_floor)):
                for leg in self.legends:
                    size = leg.get("size", self.legend_size)
                    dx = leg.get("dx", 0.0)
                    dy = leg.get("dy", 0.0)
                    with Locations((dx, dy)):
                        if leg.get("svg"):
                            add(svg_legend_sketch(leg["svg"], size))
                        else:
                            text = leg["text"]
                            font = self._legend_font_for(text, leg.get("font"))
                            Text(text, font_size=size, font=font)
            extrude(amount=z_top - z_floor)
        return cutter.part

    @property
    def _top_inner_z(self) -> float:
        """Height of the inner ceiling: the underside of the filled-in top
        block (also where the stem tube ends)."""
        return self.stem_depth + self.inner_rad

    @cached_property
    def _diffuser(self) -> "Part | None":
        """Backlit mode only: a thin transparent slab of `diffuser_depth` on the
        inner ceiling, clipped to the cavity outline so it stays inside the
        walls (leaving the opaque skirt continuous). It closes the through-hole
        glyphs from behind and diffuses the LED light."""
        if not self.legends or not self.legend_through:
            return None
        z0 = self._top_inner_z
        with BuildPart() as slab:
            with Locations((0.0, 0.0, z0)):
                Box(
                    2 * self.key_w, 2 * self.key_h, self.diffuser_depth,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                )
        diffuser = slab.part & self._outer_key_profile(shift=-self.wall)

        # Punch a clearance around the stem so the opaque top keeps a solid
        # pillar bonding it to the stem (otherwise the full-area slab severs the
        # stem post from the cap). Glyphs live in the quadrants, clear of it.
        cross = self.stem.build(self)
        cbb = cross.bounding_box()
        margin = 0.6
        with BuildPart() as clearance:
            with Locations((cbb.center().X, cbb.center().Y, z0 - self.eps)):
                Box(
                    (cbb.max.X - cbb.min.X) + 2 * margin,
                    (cbb.max.Y - cbb.min.Y) + 2 * margin,
                    self.diffuser_depth + 2 * self.eps,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                )
        return diffuser - clearance.part

    def legend_plug(self) -> "Part | None":
        """The legend plug (material 2). In flush mode: the cutter clipped by the
        solid outer profile, so its top follows the cap surface exactly. In
        backlit mode: those through-columns fused with the transparent diffuser
        slab, one connected body printed in translucent filament."""
        cutter = self._legend_cutter
        if cutter is None:
            return None
        plug = cutter & self._outer_key_profile()
        if self.legend_through and self._diffuser is not None:
            plug = plug + self._diffuser
        return plug

    def stem_guard(self) -> Part:
        """A slicer support-blocker modifier that fills the Cherry stem's inner
        cross. Load it in the slicer as a modifier volume with supports
        disabled, so no supports are generated inside the cross. Not printed as
        material; it intentionally overlaps the stem. A plain cylinder the size
        of the Cherry tube (radius `stem.stem_rad`), from the mounting face
        (z=0) up over the cross depth (`stem_depth`)."""
        with BuildPart() as guard:
            Cylinder(
                radius=self.stem.stem_rad,
                height=self.stem_depth,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
        return guard.part

    def _outer_key_profile(self, shift: float = 0.0) -> Part:
        """
        Generates the overall (non-hollow) outer shape of the key.
        This is handy for boolean operations. For example, subtracting a
        shifted profile from an un-shifted profile creates a hollow profile.

        :param shift: Distance the profile is shifted by
        """
        key_h = self.key_h + 2*shift
        key_w = self.key_w + 2*shift
        back_dy = self.back_dy + shift
        front_dy = self.front_dy + shift
        key_r = max(0.0, self.key_r + shift)

        """
        Start by constructing a trapezoidal prism.
        This is done via the intersection of two lofts.
        Each loft is between a pair of rectangular faces.
        Optionally, the front and back faces can have a curved top.
        """
        with BuildPart() as part:
            # First loft is between left and right sides (along x-axis)
            with BuildLine() as side_profile:
                Polyline(
                    (-key_h / 2 + np.tan(self.front_slope) * self.max_front_height, self.max_front_height),
                    (-key_h/2, 0),
                    (key_h/2, 0),
                    (key_h / 2 - np.tan(self.back_slope) * self.max_back_height, self.max_back_height),
                    close=True
                )
            with BuildSketch(Plane.YZ.offset(-key_w/2)):
                add(side_profile.line)
                make_face()
            with BuildSketch(Plane.YZ.offset(key_w/2)):
                add(side_profile.line)
                make_face()
            loft()

            # Project front/back heights onto un-sloped planes
            back_dx = np.tan(self.back_slope) * back_dy
            front_dx = np.tan(self.front_slope) * front_dy
            top_slope = (front_dy - back_dy) / (key_h - front_dx - back_dx)
            front_dy_proj = front_dy + top_slope * front_dx
            back_dy_proj = back_dy - top_slope * back_dx

            # Second loft is between front and back faces (along y-axis)
            with BuildSketch(Plane.XZ.offset(-key_h/2)):
                curved = abs(self.back_curve) > self.eps
                back_side_dx = np.tan(self.side_slope) * back_dy_proj
                with BuildLine():
                    Polyline(
                        (-key_w/2 + back_side_dx, back_dy_proj),
                        (-key_w/2, 0),
                        (key_w/2, 0),
                        (key_w/2 - back_side_dx, back_dy_proj),
                        close=not curved
                    )
                    if curved:
                        ThreePointArc(
                            (-key_w/2 + back_side_dx, back_dy_proj),
                            (0, back_dy_proj - self.back_curve),
                            (key_w/2 - back_side_dx, back_dy_proj)
                        )
                make_face()
            with BuildSketch(Plane.XZ.offset(key_h/2)):
                curved = abs(self.front_curve) > self.eps
                front_side_dx = np.tan(self.side_slope) * front_dy_proj
                with BuildLine():
                    Polyline(
                        (-key_w/2 + front_side_dx, front_dy_proj),
                        (-key_w/2, 0),
                        (key_w/2, 0),
                        (key_w/2 - front_side_dx, front_dy_proj),
                        close=not curved
                    )
                    if curved:
                        ThreePointArc(
                            (-key_w/2 + front_side_dx, front_dy_proj),
                            (0, front_dy_proj - self.front_curve),
                            (key_w/2 - front_side_dx, front_dy_proj)
                        )
                make_face()
            loft(mode=Mode.INTERSECT)

            # Finally, round off the edges
            if key_r > 0.0:
                edges = part.edges().group_by(Axis.Z)[1:]
                fillet(
                    sum(edges[1:], edges[0]),
                    key_r
                )
        return part.part

    def shape(self) -> Part:
        """
        Constructs the key's complete shape
        """

        # Construct hollow key shell via boolean operations
        # (avoid `offset` operation since it's completely unreliable)
        outer_profile = self._outer_key_profile()
        shell = outer_profile - self._outer_key_profile(shift=-self.wall)

        # Fill in the top of the key, so that stem is shorter, for strength
        with BuildPart() as top_block:
            with Locations((0.0, 0.0, self.stem_depth + self.inner_rad)):
                Box(
                    2*self.key_w, 2*self.key_h, self.max_height,
                    align=(Align.CENTER, Align.CENTER, Align.MIN)
                )
        filler = outer_profile & top_block.part

        # Add the stem
        cross = self.stem.build(self)
        shape = shell + filler + cross

        # Fillet some inside edges, for a bit more strength
        # (this can easily crash if `inner_rad` is too large)
        if self.inner_rad > 0.0:
            shape = shape.fillet(
                edge_list=self.stem.select_inner_rad_edges(self, shape),
                radius=self.inner_rad - self.eps,
            )
        
        if self.bump:
            with BuildPart() as bump:
                y = self.stem_depth + self.inner_rad + self.eps
                with BuildSketch(Plane.XY.offset(y)) as sketch:
                    with Locations((0, -0.2 * self.key_h)):
                        Rectangle(6, 2)
                    fillet(sketch.vertices(), 0.999)
                extrude(amount=self.max_front_height - y - 2)
            shape += bump.part

        # Carve the legend recess (material 1). Done last so it cuts through the
        # finished top surface; a no-op when the key has no legends. In backlit
        # mode the cut is a through-hole and the diffuser slab is scooped out of
        # the inner ceiling too (both handed to the transparent legend plug).
        if self._legend_cutter is not None:
            shape = shape - self._legend_cutter
            if self.legend_through and self._diffuser is not None:
                shape = shape - self._diffuser

        return shape
