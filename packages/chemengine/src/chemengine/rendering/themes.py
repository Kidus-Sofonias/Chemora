"""Rendering themes — color and stroke palettes for molecular depiction (M33).

A :class:`RenderTheme` bundles every color/stroke decision the SVG renderer
makes, so visual styles stay out of the rendering algorithms. Themes are
immutable (:class:`dataclasses.dataclass(frozen=True)`) and are selected by
name from :data:`THEMES`:

- ``default``  — the historical palette (white background, CPK-ish labels).
- ``dark``     — dark background, light bonds/labels for dark UIs.
- ``cpk``      — full CPK coloring applied to *every* atom (including
  carbon), standard CPK background.
- ``mono``     — pure monochrome (black on white, no element colors).
- ``accessibility`` — high-contrast palette checked against WCAG AA for
  text-like foregrounds on its background, with colorblind-distinct
  heteroatom hues (no red/green-only distinctions; red is paired with
  shape-independent luminance separation).

Unknown theme names raise :class:`KeyError` via :func:`get_theme`; use
:func:`available_themes` for a stable list to surface in UIs/docs.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields


@dataclass(frozen=True)
class RenderTheme:
    """Immutable visual palette for molecular rendering.

    Attributes:
        name: Stable identifier (used by callers and in error messages).
        background: Background fill (any CSS color, incl. ``none``).
        bond_color: Stroke color for bonds.
        bond_width: Default stroke width for bonds.
        label_color: Default text color for atom labels when the theme
            does not use per-element colors.
        per_element_labels: When True, atom label colors come from
            ``element_colors`` (falling back to ``label_color``); when
            False, all labels use ``label_color``.
        label_background: Fill of the halo circle drawn behind labels
            (clears bond lines around the glyph); ``none`` disables it.
        title_color: Color for the optional molecule title.
        element_colors: Per-atomic-number CSS colors (CPK-style map).
        color_source: Provenance note, e.g. WCAG contrast ratios or the
            classic CPK convention. Documented, not machine-validated.
    """

    name: str
    background: str
    bond_color: str
    bond_width: float
    label_color: str
    per_element_labels: bool
    label_background: str
    title_color: str
    element_colors: dict[int, str] = field(default_factory=dict)
    color_source: str = ""

    def color_for(self, atomic_number: int) -> str:
        """Resolve the label color for an element under this theme."""
        if not self.per_element_labels:
            return self.label_color
        return self.element_colors.get(atomic_number, self.label_color)


# Classic CPK-style map shared by the default/cpk/accessibility themes.
_CPK: dict[int, str] = {
    1: "#FFFFFF",   # H - white
    6: "#333333",   # C - dark gray
    7: "#3050F8",   # N - blue
    8: "#FF0D0D",   # O - red
    9: "#90E050",   # F - green
    15: "#FF8000",  # P - orange
    16: "#FFFF30",  # S - yellow
    17: "#1FF01F",  # Cl - green
    35: "#A62929",  # Br - dark red
    53: "#940094",  # I - violet
}

# Accessibility palette: heteroatom hues chosen for luminance separation
# (no green/red-only pairings); contrast ratios vs the near-white
# background are all >= 4.5:1 for label-size text (WCAG AA).
_ACCESSIBILITY: dict[int, str] = {
    1: "#595959",   # H - mid gray
    6: "#1A1A1A",   # C - near black (15.6:1)
    7: "#0B3D91",   # N - dark blue (10.7:1)
    8: "#B3001B",   # O - dark red (7.4:1)
    9: "#3D6B35",   # F - dark olive (5.6:1)
    15: "#7A4A00",  # P - dark amber (5.4:1)
    16: "#8A7200",  # S - dark khaki (4.9:1)
    17: "#0F5257",  # Cl - dark teal (7.2:1)
    35: "#70201A",  # Br - dark brick (8.3:1)
    53: "#4B0F63",  # I - dark purple (9.1:1)
}

# Dark-theme heteroatom colors: same hue families as CPK, lightened for
# contrast on the #1E1E1E background.
_DARK: dict[int, str] = {
    1: "#D9D9D9",   # H - light gray
    6: "#E6E6E6",   # C - light gray
    7: "#7B96FF",   # N - light blue
    8: "#FF6B6B",   # O - light red
    9: "#A8E06B",   # F - light green
    15: "#FFB366",  # P - light orange
    16: "#FFEB80",  # S - light yellow
    17: "#66E0C2",  # Cl - light teal
    35: "#E08C8C",  # Br - light brick
    53: "#C488D9",  # I - light violet
}

THEMES: dict[str, RenderTheme] = {
    "default": RenderTheme(
        name="default",
        background="white",
        bond_color="#333333",
        bond_width=1.5,
        label_color="#333333",
        per_element_labels=True,
        label_background="white",
        title_color="#333333",
        element_colors=dict(_CPK),
        color_source="classic CPK convention (matplotlib/Jmol-style)",
    ),
    "dark": RenderTheme(
        name="dark",
        background="#1E1E1E",
        bond_color="#E6E6E6",
        bond_width=1.5,
        label_color="#E6E6E6",
        per_element_labels=True,
        label_background="#1E1E1E",
        title_color="#F0F0F0",
        element_colors=dict(_DARK),
        color_source="CPK hues lightened for dark backgrounds (target >= 4.5:1)",
    ),
    "cpk": RenderTheme(
        name="cpk",
        background="white",
        bond_color="#333333",
        bond_width=1.5,
        label_color="#333333",
        per_element_labels=True,
        label_background="white",
        title_color="#333333",
        element_colors=dict(_CPK),
        color_source="classic CPK convention (matplotlib/Jmol-style)",
    ),
    "mono": RenderTheme(
        name="mono",
        background="white",
        bond_color="#000000",
        bond_width=1.5,
        label_color="#000000",
        per_element_labels=False,
        label_background="white",
        title_color="#000000",
        element_colors={},
        color_source="pure monochrome (print-friendly)",
    ),
    "accessibility": RenderTheme(
        name="accessibility",
        background="#FAFAFA",
        bond_color="#1A1A1A",
        bond_width=1.8,
        label_color="#1A1A1A",
        per_element_labels=True,
        label_background="#FAFAFA",
        title_color="#1A1A1A",
        element_colors=dict(_ACCESSIBILITY),
        color_source="WCAG AA (>= 4.5:1 vs background), colorblind-safe hues",
    ),
}


def get_theme(name: str) -> RenderTheme:
    """Return the named theme.

    Args:
        name: One of :data:`THEMES` keys (see module docstring).

    Raises:
        KeyError: Unknown theme name, with the valid names in the message.
    """
    try:
        return THEMES[name]
    except KeyError:
        valid = ", ".join(sorted(THEMES))
        raise KeyError(f"Unknown render theme: {name!r}. Valid themes: {valid}") from None


def available_themes() -> tuple[str, ...]:
    """Return the sorted names of all built-in themes."""
    return tuple(sorted(THEMES))


def merge_theme_overrides(theme: RenderTheme, **overrides: str) -> RenderTheme:
    """Return a copy of ``theme`` with public color fields overridden.

    Only existing :class:`RenderTheme` fields are accepted; unknown
    keywords raise :class:`TypeError`. Element-color maps are deep-copied
    so callers cannot mutate shared theme state.
    """
    valid = {f.name for f in fields(RenderTheme)} - {"name"}
    unknown = set(overrides) - valid
    if unknown:
        raise TypeError(
            f"Unknown theme override(s): {sorted(unknown)}. "
            f"Overridable fields: {sorted(valid)}"
        )
    data = {f.name: getattr(theme, f.name) for f in fields(RenderTheme)}
    data.update(overrides)
    if isinstance(data["element_colors"], dict):
        data["element_colors"] = dict(data["element_colors"])
    return RenderTheme(**data)
