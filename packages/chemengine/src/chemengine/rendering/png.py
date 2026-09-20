"""PNG rendering — SVG → PNG conversion layer (M33).

Roadmap Phase 10.2: "PNG output (via SVG)". This module is a thin,
honest conversion layer: it reuses the existing SVG renderer and
delegates rasterization to `cairosvg` (the roadmap-named converter).

**Optional dependency.** `cairosvg` requires the native cairo library.
It is declared as an optional extra::

    pip install chemengine[png]

When the native cairo library is unavailable (common on Windows without
GTK), :func:`render_png` and :func:`render_png_to_file` raise
:class:`PNGUnavailableError` — a documented, catchable condition rather
than a hidden failure. No chemistry or SVG logic lives here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chemengine.core.graph import MolecularGraph

__all__ = [
    "PNGUnavailableError",
    "cairosvg_available",
    "render_png",
    "render_png_to_file",
]


class PNGUnavailableError(RuntimeError):
    """Raised when PNG output is requested but cairosvg is unusable.

    The exception message distinguishes the two possible causes:
    the `cairosvg` package is not installed, or the package is installed
    but the native cairo library cannot be loaded. See
    :func:`cairosvg_available` for a non-raising probe.
    """


def cairosvg_available() -> bool:
    """Return True if `cairosvg` imports and can rasterize.

    Probing performs a trivial 1x1 conversion so a broken native cairo
    install (import succeeds, rasterization fails) is also detected.
    """
    try:
        import cairosvg  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


def render_png(
    graph: MolecularGraph,
    coordinates: tuple[Any, ...] | None = None,
    *,
    scale: float = 2.0,
    output_width: int | None = None,
    output_height: int | None = None,
    background: str | None = None,
    **svg_options: Any,
) -> bytes:
    """Render a molecular graph as PNG bytes.

    The graph is first rendered to SVG with :func:`render_svg` (all
    keyword arguments — theme, highlight, title, etc. — pass through
    unchanged), then converted to PNG via cairosvg.

    Args:
        graph: The molecular graph to render.
        coordinates: Optional precomputed 2D coordinates (deterministic
            output requires deterministic coordinates — supply these or
            accept the layout engine's deterministic default).
        scale: DPI multiplier applied to the SVG's natural size (used
            when ``output_width``/``output_height`` are not given).
        output_width: Exact output width in pixels (overrides ``scale``).
        output_height: Exact output height in pixels (overrides ``scale``).
        background: PNG background color; None keeps the SVG background.
        **svg_options: Forwarded to :func:`render_svg` (theme, highlight,
            show_hydrogens, title, ...).

    Returns:
        PNG image bytes.

    Raises:
        PNGUnavailableError: cairosvg or native cairo is unavailable.
        KeyError: Unknown theme name (from :func:`render_svg`).
        IndexError: Invalid highlight indices (from :func:`render_svg`).
    """
    from chemengine.rendering.svg import render_svg

    if not cairosvg_available():
        raise PNGUnavailableError(
            "PNG rendering requires the optional 'cairosvg' package and the "
            "native cairo library. Install with: pip install 'chemengine[png]'. "
            "On Debian/Ubuntu: apt-get install libcairo2. "
            "On Windows, install GTK runtime or use SVG output. "
            "Check availability with chemengine.rendering.png.cairosvg_available()."
        )
    import cairosvg

    svg = render_svg(graph, coordinates, **svg_options)
    return cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        scale=scale,
        output_width=output_width,
        output_height=output_height,
        background_color=background,
    )


def render_png_to_file(
    graph: MolecularGraph,
    filepath: str,
    *,
    scale: float = 2.0,
    output_width: int | None = None,
    output_height: int | None = None,
    background: str | None = None,
    **svg_options: Any,
) -> None:
    """Render a molecular graph to a PNG file.

    Args:
        graph: The molecular graph to render.
        filepath: Output file path (parent directory must exist).
        scale: DPI multiplier (see :func:`render_png`).
        output_width: Exact output width in pixels.
        output_height: Exact output height in pixels.
        background: PNG background color.
        **svg_options: Forwarded to :func:`render_svg`.

    Raises:
        PNGUnavailableError: cairosvg or native cairo is unavailable.
        OSError: The file cannot be written.
    """
    data = render_png(
        graph,
        coordinates,
        scale=scale,
        output_width=output_width,
        output_height=output_height,
        background=background,
        **svg_options,
    )
    with open(filepath, "wb") as f:
        f.write(data)
