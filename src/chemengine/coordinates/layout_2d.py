"""2D Coordinate Generation — Force-directed layout with ring templates.

Implements:
- Fruchterman-Reingold force-directed algorithm for acyclic portions
- Ring template placement for common ring sizes (3-8 membered)
- Bond length/angle constraints
- Collision avoidance
"""

from __future__ import annotations

import math
import random

from chemengine.core.enums import BondOrder
from chemengine.core.geometry import Coordinate2D
from chemengine.core.graph import MolecularGraph

# ── Constants ──

BOND_LENGTH_2D: float = 1.5
RING_RADIUS: dict[int, float] = {
    3: 0.9,
    4: 1.3,
    5: 1.6,
    6: 1.8,
    7: 2.1,
    8: 2.3,
}
DEFAULT_ITERATIONS: int = 100
REPULSION_STRENGTH: float = 100.0
ATTRACTION_STRENGTH: float = 0.1
DAMPING: float = 0.95
MIN_SEPARATION: float = 0.5


# ── Ring Detection ──

def _find_rings(graph: MolecularGraph) -> list[list[int]]:
    """Find all simple rings using DFS cycle detection (max size 8)."""
    n = graph.num_atoms
    if n == 0:
        return []
    adj: dict[int, list[int]] = {i: [] for i in range(n)}
    for bond in graph.bonds:
        adj[bond.atom1].append(bond.atom2)
        adj[bond.atom2].append(bond.atom1)

    seen_rings: set[tuple[int, ...]] = set()
    rings: list[list[int]] = []
    max_ring_size = 8

    def dfs(start: int, current: int, path: list[int], visited: set[int]) -> None:
        for neighbor in adj[current]:
            if neighbor == start and len(path) >= 3:
                ring_key = tuple(sorted(path))
                if ring_key not in seen_rings:
                    seen_rings.add(ring_key)
                    rings.append(list(path))
            elif neighbor not in visited and neighbor > start and len(path) < max_ring_size:
                visited.add(neighbor)
                path.append(neighbor)
                dfs(start, neighbor, path, visited)
                path.pop()
                visited.discard(neighbor)

    for start in range(n):
        dfs(start, start, [start], {start})

    return rings


def _find_fused_ring_systems(graph: MolecularGraph) -> list[list[int]]:
    """Find ring systems (connected rings sharing atoms)."""
    rings = _find_rings(graph)
    if not rings:
        return []

    # Build adjacency between rings
    ring_sets = [set(r) for r in rings]
    n_rings = len(rings)
    parent = list(range(n_rings))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n_rings):
        for j in range(i + 1, n_rings):
            if ring_sets[i] & ring_sets[j]:
                union(i, j)

    systems: dict[int, list[int]] = {}
    for i in range(n_rings):
        root = find(i)
        if root not in systems:
            systems[root] = []
        systems[root].extend(rings[i])

    return [list(set(atoms)) for atoms in systems.values()]


# ── Ring Template Placement ──

def _place_ring(ring_atoms: list[int], center_x: float, center_y: float,
                radius: float) -> dict[int, Coordinate2D]:
    """Place ring atoms in a regular polygon around a center point."""
    coords: dict[int, Coordinate2D] = {}
    n = len(ring_atoms)
    for i, atom_idx in enumerate(ring_atoms):
        angle = 2 * math.pi * i / n - math.pi / 2  # Start from top
        coords[atom_idx] = Coordinate2D(
            center_x + radius * math.cos(angle),
            center_y + radius * math.sin(angle),
        )
    return coords


# ── Force-Directed Layout ──

def _initialize_positions(graph: MolecularGraph, seed: int | None = None) -> list[Coordinate2D]:
    """Initialize atom positions randomly in a circle."""
    rng = random.Random(seed)
    n = graph.num_atoms
    radius = math.sqrt(n) * BOND_LENGTH_2D
    return [
        Coordinate2D(
            radius * math.cos(2 * math.pi * i / n) + rng.uniform(-0.1, 0.1),
            radius * math.sin(2 * math.pi * i / n) + rng.uniform(-0.1, 0.1),
        )
        for i in range(n)
    ]


def _force_directed_step(
    positions: list[Coordinate2D],
    graph: MolecularGraph,
    temperature: float,
) -> list[Coordinate2D]:
    """Perform one step of the Fruchterman-Reingold algorithm."""
    n = graph.num_atoms
    forces = [(0.0, 0.0)] * n

    # Repulsive forces between all pairs
    for i in range(n):
        for j in range(i + 1, n):
            dx = positions[i].x - positions[j].x
            dy = positions[i].y - positions[j].y
            dist = math.sqrt(dx * dx + dy * dy) + 1e-6
            force = REPULSION_STRENGTH / (dist * dist)
            fx = (dx / dist) * force
            fy = (dy / dist) * force
            forces[i] = (forces[i][0] + fx, forces[i][1] + fy)
            forces[j] = (forces[j][0] - fx, forces[j][1] - fy)

    # Attractive forces along bonds
    for bond in graph.bonds:
        i, j = bond.atom1, bond.atom2
        dx = positions[i].x - positions[j].x
        dy = positions[i].y - positions[j].y
        dist = math.sqrt(dx * dx + dy * dy) + 1e-6
        ideal_length = BOND_LENGTH_2D
        if bond.order == BondOrder.DOUBLE:
            ideal_length *= 0.95
        elif bond.order == BondOrder.TRIPLE:
            ideal_length *= 0.9
        force = (dist - ideal_length) * ATTRACTION_STRENGTH
        fx = (dx / dist) * force
        fy = (dy / dist) * force
        forces[i] = (forces[i][0] - fx, forces[i][1] - fy)
        forces[j] = (forces[j][0] + fx, forces[j][1] + fy)

    # Apply forces with temperature-based displacement
    new_positions = []
    for i in range(n):
        fx, fy = forces[i]
        dist = math.sqrt(fx * fx + fy * fy) + 1e-6
        displacement = min(dist, temperature)
        nx = positions[i].x + (fx / dist) * displacement
        ny = positions[i].y + (fy / dist) * displacement
        new_positions.append(Coordinate2D(nx, ny))

    return new_positions


def force_directed_layout(
    graph: MolecularGraph,
    iterations: int = DEFAULT_ITERATIONS,
    seed: int | None = None,
) -> list[Coordinate2D]:
    """Compute 2D coordinates using the Fruchterman-Reingold force-directed algorithm.

    Args:
        graph: The molecular graph.
        iterations: Number of algorithm iterations.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of Coordinate2D, one per atom.
    """
    if graph.num_atoms == 0:
        return ()
    if graph.num_atoms == 1:
        return (Coordinate2D(0.0, 0.0),)

    positions = list(_initialize_positions(graph, seed))
    temperature = BOND_LENGTH_2D * 10.0

    for _ in range(iterations):
        positions = _force_directed_step(positions, graph, temperature)
        temperature *= DAMPING

    return tuple(positions)


# ── Combined Layout (Rings + Force-Directed) ──

def generate_2d_coordinates(
    graph: MolecularGraph,
    iterations: int = DEFAULT_ITERATIONS,
    seed: int | None = None,
) -> tuple[Coordinate2D, ...]:
    """Generate 2D coordinates for a molecular graph.

    Combines ring template placement for cyclic portions with
    force-directed layout for the full molecule.

    Args:
        graph: The molecular graph.
        iterations: Force-directed iterations (after template placement).
        seed: Random seed for reproducibility.

    Returns:
        Tuple of Coordinate2D, one per atom.
    """
    if graph.num_atoms == 0:
        return ()
    if graph.num_atoms == 1:
        return (Coordinate2D(0.0, 0.0),)

    n = graph.num_atoms
    placed: set[int] = set()
    coords: dict[int, Coordinate2D] = {}

    # Find and place ring systems
    ring_atoms_list = _find_rings(graph)

    # Sort rings: largest first, then by node set
    ring_atoms_list.sort(key=lambda r: (-len(r), tuple(sorted(r))))

    cx, cy = 0.0, 0.0
    for ring in ring_atoms_list:
        ring_size = len(ring)
        if ring_size < 3 or ring_size > 8:
            continue
        radius = RING_RADIUS.get(ring_size, ring_size * 0.3)
        ring_coords = _place_ring(ring, cx, cy, radius)
        coords.update(ring_coords)
        placed.update(ring)
        # Offset center for next ring system
        cx += radius * 3.0

    # Start with template positions, then run force-directed to refine
    if placed:
        # Initialize positions from templates
        full_positions = list(_initialize_positions(graph, seed))
        for idx, coord in coords.items():
            full_positions[idx] = coord

        # Run force-directed from the template-initialized positions
        temperature = BOND_LENGTH_2D * 5.0
        for _ in range(iterations):
            full_positions = _force_directed_step(full_positions, graph, temperature)
            temperature *= DAMPING

        return tuple(full_positions)
    else:
        return force_directed_layout(graph, iterations, seed)
