"""SVG Molecular Depiction — 2D rendering of molecular graphs.

Renders molecular structures as SVG with:
- Single, double, and triple bonds
- Atom labels (element symbols)
- Wedge/dash bonds for stereochemistry
- Aromatic bond circles
- Configurable bond length, atom colors, font sizes
"""

from __future__ import annotations

import math
from typing import Any

from chemengine.core.enums import BondOrder
from chemengine.core.geometry import Coordinate2D
from chemengine.core.graph import MolecularGraph

# ── Constants ──

DEFAULT_BOND_LENGTH: float = 40.0
DEFAULT_ATOM_RADIUS: float = 15.0
DEFAULT_FONT_SIZE: float = 12.0
DEFAULT_PADDING: float = 30.0
WEDGE_WIDTH: float = 6.0

# Element colors (CPK-like)
ELEMENT_COLORS: dict[int, str] = {
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

# Elements that should show explicit labels
EXPLICIT_LABEL_ELEMENTS: set[int] = {
    1,  # H (when shown)
    7, 8, 9, 15, 16, 17, 35, 53,  # All heteroatoms
}


def _should_show_label(atom_index: int, graph: MolecularGraph) -> bool:
    """Determine if an atom should show an explicit label."""
    atom = graph.atoms[atom_index]
    z = atom.atomic_number
    # Always show heteroatoms and hydrogens
    if z in EXPLICIT_LABEL_ELEMENTS:
        return True
    # Show carbon only if degree != 2 or has charge
    if z == 6:
        if atom.formal_charge != 0:
            return True
        degree = graph.get_degree(atom_index)
        if degree != 2:
            return True
        return False
    return True


def _get_color(atomic_number: int) -> str:
    """Get SVG color for an element."""
    return ELEMENT_COLORS.get(atomic_number, "#333333")


def _coord_to_svg(coord: Coordinate2D, offset_x: float, offset_y: float,
                  scale: float) -> tuple[float, float]:
    """Convert molecular coordinates to SVG coordinates."""
    return (
        offset_x + coord.x * scale,
        offset_y - coord.y * scale,  # Flip Y axis
    )


# ── Bond Rendering ──

def _render_single_bond(
    x1: float, y1: float, x2: float, y2: float,
    color: str = "#333333", width: float = 1.5,
) -> str:
    """Render a single bond as a line."""
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>\n'


def _render_double_bond(
    x1: float, y1: float, x2: float, y2: float,
    color: str = "#333333", width: float = 1.5,
) -> str:
    """Render a double bond as two parallel lines."""
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy) + 1e-10
    # Perpendicular offset
    px = -dy / length * 2.0
    py = dx / length * 2.0
    return (
        f'<line x1="{x1 + px:.2f}" y1="{y1 + py:.2f}" x2="{x2 + px:.2f}" y2="{y2 + py:.2f}" '
        f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>\n'
        f'<line x1="{x1 - px:.2f}" y1="{y1 - py:.2f}" x2="{x2 - px:.2f}" y2="{y2 - py:.2f}" '
        f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>\n'
    )


def _render_triple_bond(
    x1: float, y1: float, x2: float, y2: float,
    color: str = "#333333", width: float = 1.5,
) -> str:
    """Render a triple bond as three parallel lines."""
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy) + 1e-10
    px = -dy / length * 2.5
    py = dx / length * 2.5
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>\n'
        f'<line x1="{x1 + px:.2f}" y1="{y1 + py:.2f}" x2="{x2 + px:.2f}" y2="{y2 + py:.2f}" '
        f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>\n'
        f'<line x1="{x1 - px:.2f}" y1="{y1 - py:.2f}" x2="{x2 - px:.2f}" y2="{y2 - py:.2f}" '
        f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>\n'
    )


def _render_wedge_bond(
    x1: float, y1: float, x2: float, y2: float,
    color: str = "#333333",
) -> str:
    """Render a wedge bond (solid triangle pointing toward viewer)."""
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy) + 1e-10
    px = -dy / length * WEDGE_WIDTH
    py = dx / length * WEDGE_WIDTH
    return (
        f'<polygon points="{x1:.2f},{y1:.2f} {x2 + px:.2f},{y2 + py:.2f} {x2 - px:.2f},{y2 - py:.2f}" '
        f'fill="{color}" stroke="none"/>\n'
    )


def _render_dashed_bond(
    x1: float, y1: float, x2: float, y2: float,
    color: str = "#333333", width: float = 1.5,
) -> str:
    """Render a dashed bond (hatched, pointing away from viewer)."""
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy) + 1e-10
    px = -dy / length
    py = dx / length
    num_dashes = 5
    svg = ""
    for i in range(num_dashes):
        t = (i + 0.5) / num_dashes
        cx = x1 + dx * t
        cy = y1 + dy * t
        half_w = WEDGE_WIDTH * t
        x_start = cx + px * half_w
        y_start = cy + py * half_w
        x_end = cx - px * half_w
        y_end = cy - py * half_w
        svg += f'<line x1="{x_start:.2f}" y1="{y_start:.2f}" x2="{x_end:.2f}" y2="{y_end:.2f}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>\n'
    return svg


def _render_aromatic_bond(
    x1: float, y1: float, x2: float, y2: float,
    color: str = "#333333", width: float = 1.5,
) -> str:
    """Render an aromatic bond (solid line + dashed inner line)."""
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy) + 1e-10
    px = -dy / length * 2.0
    py = dx / length * 2.0
    # Outer solid line
    svg = (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>\n'
    )
    # Inner dashed line
    svg += (
        f'<line x1="{x1 + px:.2f}" y1="{y1 + py:.2f}" x2="{x2 + px:.2f}" y2="{y2 + py:.2f}" '
        f'stroke="{color}" stroke-width="{width * 0.6}" stroke-linecap="round" '
        f'stroke-dasharray="3,3"/>\n'
    )
    return svg


# ── Atom Label Rendering ──

def _render_atom_label(
    x: float, y: float, label: str, color: str,
    font_size: float = DEFAULT_FONT_SIZE,
    charge: int = 0,
) -> str:
    """Render an atom label with optional charge annotation."""
    svg = ""
    # Background circle to clear bond lines
    svg += f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{DEFAULT_ATOM_RADIUS:.2f}" fill="white" stroke="none"/>\n'
    # Element symbol
    svg += (
        f'<text x="{x:.2f}" y="{y + font_size * 0.35:.2f}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="{font_size:.2f}" '
        f'fill="{color}" text-anchor="middle" dominant-baseline="central">{label}</text>\n'
    )
    # Charge annotation
    if charge != 0:
        charge_str = f"{charge:+d}" if abs(charge) == 1 else f"{charge:+d}"
        svg += (
            f'<text x="{x + font_size * 0.5:.2f}" y="{y - font_size * 0.3:.2f}" '
            f'font-family="Arial, Helvetica, sans-serif" font-size="{font_size * 0.6:.2f}" '
            f'fill="{color}" text-anchor="start">{charge_str}</text>\n'
        )
    return svg


# ── Main Renderer ──

def render_svg(
    graph: MolecularGraph,
    coordinates: tuple[Coordinate2D, ...] | None = None,
    *,
    bond_length: float = DEFAULT_BOND_LENGTH,
    show_hydrogens: bool = False,
    padding: float = DEFAULT_PADDING,
    title: str | None = None,
) -> str:
    """Render a molecular graph as an SVG string.

    Args:
        graph: The molecular graph to render.
        coordinates: 2D coordinates. If None, generates using force-directed layout.
        bond_length: Bond length in SVG units (for scaling).
        show_hydrogens: Whether to render hydrogen atoms explicitly.
        padding: Padding around the molecule in SVG units.
        title: Optional title to add above the molecule.

    Returns:
        Complete SVG string.
    """
    from chemengine.coordinates.layout_2d import generate_2d_coordinates

    if graph.num_atoms == 0:
        return _empty_svg()

    # Generate or use provided coordinates
    if coordinates is None:
        coordinates = generate_2d_coordinates(graph)

    if len(coordinates) != graph.num_atoms:
        raise ValueError(
            f"Coordinate count ({len(coordinates)}) doesn't match "
            f"atom count ({graph.num_atoms})"
        )

    # Compute bounding box
    min_x = min(c.x for c in coordinates)
    max_x = max(c.x for c in coordinates)
    min_y = min(c.y for c in coordinates)
    max_y = max(c.y for c in coordinates)

    mol_width = max_x - min_x if max_x > min_x else 1.0
    mol_height = max_y - min_y if max_y > min_y else 1.0

    # Scale to fit bond_length
    if graph.num_bonds > 0:
        avg_bond_len = sum(
            coordinates[b.atom1].distance_to(coordinates[b.atom2])
            for b in graph.bonds
        ) / graph.num_bonds
        if avg_bond_len > 0:
            scale = bond_length / avg_bond_len
        else:
            scale = 1.0
    else:
        scale = 1.0

    # Compute SVG dimensions
    svg_width = mol_width * scale + 2 * padding + 2 * DEFAULT_ATOM_RADIUS
    svg_height = mol_height * scale + 2 * padding + 2 * DEFAULT_ATOM_RADIUS

    # Offset to center molecule
    offset_x = padding + DEFAULT_ATOM_RADIUS - min_x * scale
    offset_y = padding + DEFAULT_ATOM_RADIUS + max_y * scale

    # Start SVG
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width:.1f}" height="{svg_height:.1f}" viewBox="0 0 {svg_width:.1f} {svg_height:.1f}">\n'
    svg += '<rect width="100%" height="100%" fill="white"/>\n'

    # Title
    if title:
        svg += f'<text x="{svg_width / 2:.1f}" y="{padding * 0.6:.1f}" font-family="Arial, Helvetica, sans-serif" font-size="14" fill="#333" text-anchor="middle">{_escape_xml(title)}</text>\n'

    # Render bonds
    for bond in graph.bonds:
        x1, y1 = _coord_to_svg(coordinates[bond.atom1], offset_x, offset_y, scale)
        x2, y2 = _coord_to_svg(coordinates[bond.atom2], offset_x, offset_y, scale)
        color = "#333333"

        # Check for stereochemistry on the atom (wedge/dash)
        atom1_stereo = graph.atoms[bond.atom1].stereochemistry
        is_wedge = atom1_stereo.value in ("@", "R") if atom1_stereo else False
        is_dash = atom1_stereo.value in ("@@", "S") if atom1_stereo else False

        if bond.is_aromatic:
            svg += _render_aromatic_bond(x1, y1, x2, y2, color)
        elif bond.order == BondOrder.TRIPLE:
            svg += _render_triple_bond(x1, y1, x2, y2, color)
        elif bond.order == BondOrder.DOUBLE:
            svg += _render_double_bond(x1, y1, x2, y2, color)
        elif is_wedge:
            svg += _render_wedge_bond(x1, y1, x2, y2, color)
        elif is_dash:
            svg += _render_dashed_bond(x1, y1, x2, y2, color)
        else:
            svg += _render_single_bond(x1, y1, x2, y2, color)

    # Render atom labels
    for i, coord in enumerate(coordinates):
        atom = graph.atoms[i]
        z = atom.atomic_number

        # Skip hydrogens unless explicitly requested
        if z == 1 and not show_hydrogens:
            continue

        if not _should_show_label(i, graph) and z == 6:
            continue

        x, y = _coord_to_svg(coord, offset_x, offset_y, scale)
        color = _get_color(z)
        label = atom.symbol
        svg += _render_atom_label(x, y, label, color, DEFAULT_FONT_SIZE, atom.formal_charge)

    svg += "</svg>"
    return svg


def render_svg_to_file(
    graph: MolecularGraph,
    filepath: str,
    **options: Any,
) -> None:
    """Render a molecular graph to an SVG file.

    Args:
        graph: The molecular graph to render.
        filepath: Output file path.
        **options: Additional options passed to render_svg().
    """
    svg = render_svg(graph, **options)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(svg)


def _empty_svg() -> str:
    """Render an empty SVG placeholder."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<text x="50" y="50" text-anchor="middle" fill="#999">Empty</text></svg>'
    )


def _escape_xml(text: str) -> str:
    """Escape special XML characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
