from build123d import *
import numpy as np
from dataclasses import dataclass, field
from functools import cached_property
from stem import Stem


SYMBOL_GLYPHS = {"⇥", "⌫", "⏎", "⇧"}


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

        # Top-surface height at the key center; the flat cutter floor sits
        # `legend_depth` below it (recess depth ~uniform on the near-flat top).
        h_center = (self.front_dy + self.back_dy) / 2.0
        z_floor = h_center - self.legend_depth
        z_top = self.max_height + 1.0            # safely above the tallest corner

        with BuildPart() as cutter:
            with BuildSketch(Plane.XY.offset(z_floor)):
                for leg in self.legends:
                    text = leg["text"]
                    size = leg.get("size", self.legend_size)
                    dx = leg.get("dx", 0.0)
                    dy = leg.get("dy", 0.0)
                    font = self._legend_font_for(text, leg.get("font"))
                    with Locations((dx, dy)):
                        Text(text, font_size=size, font=font)
            extrude(amount=z_top - z_floor)
        return cutter.part

    def legend_plug(self) -> "Part | None":
        """The flush legend plug (material 2): the cutter clipped by the solid
        outer profile, so its top follows the cap surface exactly."""
        cutter = self._legend_cutter
        if cutter is None:
            return None
        return cutter & self._outer_key_profile()

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
        # finished top surface; a no-op when the key has no legends.
        if self._legend_cutter is not None:
            shape = shape - self._legend_cutter

        return shape
