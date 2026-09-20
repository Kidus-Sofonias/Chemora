"""Molecular rendering — SVG/PNG depiction and visual themes.

Modules:
    svg: SVG molecular depiction with bond rendering and atom labels
    png: SVG → PNG conversion (optional cairosvg dependency)
    themes: Named rendering themes (default/dark/cpk/mono/accessibility)
"""

from chemengine.rendering.svg import (
    SubstructureHighlight,
    render_svg,
    render_svg_to_file,
)
from chemengine.rendering.themes import (
    RenderTheme,
    available_themes,
    get_theme,
)

__all__ = [
    "RenderTheme",
    "SubstructureHighlight",
    "available_themes",
    "get_theme",
    "render_svg",
    "render_svg_to_file",
]
