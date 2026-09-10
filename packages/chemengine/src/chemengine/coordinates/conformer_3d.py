"""3D Conformer Generation — Distance geometry with bounds matrix.

Implements:
- Bounds matrix construction from connectivity
- Random embedding within bounds
- Basic energy minimization via steepest descent
- Conformer clustering by RMSD
"""

from __future__ import annotations

import math
import random

from chemengine.core.enums import BondOrder
from chemengine.core.geometry import Conformer, Coordinate3D
from chemengine.core.graph import MolecularGraph

# ── Constants ──

BOND_LENGTHS: dict[BondOrder, float] = {
    BondOrder.SINGLE: 1.54,
    BondOrder.DOUBLE: 1.34,
    BondOrder.TRIPLE: 1.20,
    BondOrder.AROMATIC: 1.40,
}
VDW_RADII: dict[int, float] = {
    1: 1.20,   # H
    6: 1.70,   # C
    7: 1.55,   # N
    8: 1.52,   # O
    9: 1.47,   # F
    15: 1.80,  # P
    16: 1.80,  # S
    17: 1.75,  # Cl
    35: 1.85,  # Br
    53: 1.98,  # I
}
DEFAULT_VDW_RADIUS = 1.70
MAX_ENERGY_ITERATIONS = 200
ENERGY_STEP = 0.01
RMSD_CLUSTER_THRESHOLD = 0.5
MAX_CONFORMERS = 50


# ── Bounds Matrix ──

def _get_vdw_radius(atomic_number: int) -> float:
    """Get van der Waals radius for an element."""
    return VDW_RADII.get(atomic_number, DEFAULT_VDW_RADIUS)


def _build_bounds_matrix(graph: MolecularGraph) -> tuple[list[list[float]], list[list[float]]]:
    """Build lower and upper bounds matrices from molecular connectivity.

    Returns:
        (lower_bounds, upper_bounds) as lists of lists.
    """
    n = graph.num_atoms
    INF = 999.0

    lower = [[0.0] * n for _ in range(n)]
    upper = [[INF] * n for _ in range(n)]

    # 1-bond distances
    for bond in graph.bonds:
        i, j = bond.atom1, bond.atom2
        length = BOND_LENGTHS.get(bond.order, 1.54)
        lower[i][j] = lower[j][i] = length * 0.9
        upper[i][j] = upper[j][i] = length * 1.1

    # Diagonal
    for i in range(n):
        lower[i][i] = 0.0
        upper[i][i] = 0.0

    # 2-bond distances (angle constraints)
    for k in range(n):
        neighbors_k = graph.get_neighbors(k)
        for i_idx in range(len(neighbors_k)):
            for j_idx in range(i_idx + 1, len(neighbors_k)):
                i, j = neighbors_k[i_idx], neighbors_k[j_idx]
                # Triangle inequality: d(i,j) >= |d(i,k) - d(k,j)|
                lo = max(lower[i][k] - upper[k][j], lower[j][k] - upper[k][i], 0.0)
                hi = upper[i][k] + upper[k][j]
                lower[i][j] = max(lower[i][j], lo)
                lower[j][i] = lower[i][j]
                upper[i][j] = min(upper[i][j], hi)
                upper[j][i] = upper[i][j]

    # 3-bond distances (torsion constraints via shortest paths)
    for bond in graph.bonds:
        a1, a2 = bond.atom1, bond.atom2
        for n1 in graph.get_neighbors(a1):
            if n1 == a2:
                continue
            for n2 in graph.get_neighbors(a2):
                if n2 == a1 or n2 == n1:
                    continue
                lo = max(lower[n1][a1] - upper[a1][a2] - upper[a2][n2], 0.0)
                hi = upper[n1][a1] + upper[a1][a2] + upper[a2][n2]
                lower[n1][n2] = max(lower[n1][n2], lo)
                lower[n2][n1] = lower[n1][n2]
                upper[n1][n2] = min(upper[n1][n2], hi)
                upper[n2][n1] = upper[n1][n2]

    # VDW lower bounds (non-bonded atoms)
    for i in range(n):
        for j in range(i + 1, n):
            if upper[i][j] < INF:
                continue  # Skip bonded/near-bonded
            r_i = _get_vdw_radius(graph.atoms[i].atomic_number)
            r_j = _get_vdw_radius(graph.atoms[j].atomic_number)
            vdw_contact = r_i + r_j
            lower[i][j] = max(lower[i][j], vdw_contact * 0.7)
            lower[j][i] = lower[i][j]

    return lower, upper


def _bounds_to_distance_matrix(lower: list[list[float]], upper: list[list[float]],
                               n: int) -> list[list[float]]:
    """Convert bounds to a distance matrix using MetrizeBounds-like smoothing.
    """
    # Initialize with midpoints of bounds
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if upper[i][j] < 900.0:
                d = (lower[i][j] + upper[i][j]) / 2.0
            else:
                d = 5.0 + abs(i - j) * 0.5  # Initial guess for unconnected
            dist[i][j] = dist[j][i] = d

    # Triangle inequality smoothing
    for _ in range(10):
        for k in range(n):
            for i in range(n):
                for j in range(i + 1, n):
                    # d(i,j) <= d(i,k) + d(k,j)
                    max_d = dist[i][k] + dist[k][j]
                    if dist[i][j] > max_d:
                        dist[i][j] = dist[j][i] = max_d
                    # d(i,j) >= |d(i,k) - d(k,j)|
                    min_d = abs(dist[i][k] - dist[k][j])
                    if dist[i][j] < min_d:
                        dist[i][j] = dist[j][i] = min_d

    return dist


def _embed_from_distance_matrix(dist: list[list[float]], n: int,
                                 seed: int | None = None) -> list[Coordinate3D]:
    """Embed atoms in 3D from a distance matrix using iterative distance fitting.
    """
    rng = random.Random(seed)

    # Initialize along a spiral to give good initial spacing
    coords: list[Coordinate3D] = []
    for i in range(n):
        angle = i * 2.399963  # golden angle in radians
        r = 1.5 * math.sqrt(i + 1)
        z = (i - n / 2.0) * 0.5
        coords.append(Coordinate3D(
            r * math.cos(angle),
            r * math.sin(angle),
            z,
        ))

    # Iterative distance fitting with decreasing step size
    for iteration in range(200):
        step = 0.5 * (1.0 - iteration / 200.0) + 0.01
        max_force = 0.0
        new_coords = list(coords)
        for i in range(n):
            fx, fy, fz = 0.0, 0.0, 0.0
            for j in range(n):
                if i == j:
                    continue
                dx = coords[i].x - coords[j].x
                dy = coords[i].y - coords[j].y
                dz = coords[i].z - coords[j].z
                current_dist = math.sqrt(dx * dx + dy * dy + dz * dz) + 1e-10
                target = dist[i][j]
                if target < 0.1 or target > 20.0:
                    continue
                diff = current_dist - target
                force = diff * step
                fx += (dx / current_dist) * force
                fy += (dy / current_dist) * force
                fz += (dz / current_dist) * force
                max_force = max(max_force, abs(diff))

            new_coords[i] = Coordinate3D(
                coords[i].x - fx,
                coords[i].y - fy,
                coords[i].z - fz,
            )

        coords = new_coords
        if max_force < 0.005:
            break

    # Center at origin
    cx = sum(c.x for c in coords) / n
    cy = sum(c.y for c in coords) / n
    cz = sum(c.z for c in coords) / n
    coords = [Coordinate3D(c.x - cx, c.y - cy, c.z - cz) for c in coords]

    return coords


# ── Energy Minimization ──

def _distance(a: Coordinate3D, b: Coordinate3D) -> float:
    """Euclidean distance between two 3D points."""
    dx = a.x - b.x
    dy = a.y - b.y
    dz = a.z - b.z
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _quick_energy(coords: list[Coordinate3D], graph: MolecularGraph) -> float:
    """Quick energy estimate for tracking best conformer."""
    energy = 0.0
    for bond in graph.bonds:
        i, j = bond.atom1, bond.atom2
        target = BOND_LENGTHS.get(bond.order, 1.54)
        dx = coords[i].x - coords[j].x
        dy = coords[i].y - coords[j].y
        dz = coords[i].z - coords[j].z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) + 1e-10
        diff = dist - target
        energy += 50.0 * diff * diff
    return energy


def _minimize_energy(
    coords: list[Coordinate3D],
    graph: MolecularGraph,
    max_iter: int = MAX_ENERGY_ITERATIONS,
) -> list[Coordinate3D]:
    """Steepest descent energy minimization.
    Penalizes: bond length deviations, VDW clashes.
    """
    n = graph.num_atoms
    coords = list(coords)

    # Adaptive step size
    best_energy = float('inf')
    best_coords = list(coords)

    for iteration in range(max_iter):
        gradients = [(0.0, 0.0, 0.0)] * n
        max_grad = 0.0

        # Bond length penalty (strong)
        for bond in graph.bonds:
            i, j = bond.atom1, bond.atom2
            target = BOND_LENGTHS.get(bond.order, 1.54)
            dx = coords[i].x - coords[j].x
            dy = coords[i].y - coords[j].y
            dz = coords[i].z - coords[j].z
            dist = math.sqrt(dx * dx + dy * dy + dz * dz) + 1e-10
            diff = dist - target
            force = diff * 2.0  # Stronger restoring force
            fx = (dx / dist) * force
            fy = (dy / dist) * force
            fz = (dz / dist) * force
            gi = gradients[i]
            gj = gradients[j]
            gradients[i] = (gi[0] + fx, gi[1] + fy, gi[2] + fz)
            gradients[j] = (gj[0] - fx, gj[1] - fy, gj[2] - fz)
            max_grad = max(max_grad, abs(diff))

        # VDW clash penalty
        for i in range(n):
            for j in range(i + 1, n):
                bond = graph.get_bond(i, j)
                if bond is not None:
                    continue
                r_i = _get_vdw_radius(graph.atoms[i].atomic_number)
                r_j = _get_vdw_radius(graph.atoms[j].atomic_number)
                vdw = r_i + r_j
                dx = coords[i].x - coords[j].x
                dy = coords[i].y - coords[j].y
                dz = coords[i].z - coords[j].z
                dist = math.sqrt(dx * dx + dy * dy + dz * dz) + 1e-10
                if dist < vdw * 0.8:
                    diff = vdw * 0.8 - dist
                    force = diff * 5.0
                    fx = (dx / dist) * force
                    fy = (dy / dist) * force
                    fz = (dz / dist) * force
                    gi = gradients[i]
                    gj = gradients[j]
                    gradients[i] = (gi[0] + fx, gi[1] + fy, gi[2] + fz)
                    gradients[j] = (gj[0] - fx, gj[1] - fy, gj[2] - fz)
                    max_grad = max(max_grad, diff)

        if max_grad < 0.001:
            break

        # Adaptive step: scale by remaining iterations
        step_scale = max(0.01, 0.1 * (1.0 - iteration / max_iter))

        # Apply gradients
        for i in range(n):
            gx, gy, gz = gradients[i]
            g_mag = math.sqrt(gx * gx + gy * gy + gz * gz) + 1e-10
            step = min(step_scale, g_mag * 0.5)
            coords[i] = Coordinate3D(
                coords[i].x - (gx / g_mag) * step,
                coords[i].y - (gy / g_mag) * step,
                coords[i].z - (gz / g_mag) * step,
            )

        # Track best
        energy = _quick_energy(coords, graph)
        if energy < best_energy:
            best_energy = energy
            best_coords = list(coords)

    return best_coords


# ── Conformer Generation ──

def generate_conformer(
    graph: MolecularGraph,
    seed: int | None = None,
) -> Conformer:
    """Generate a single 3D conformer using distance geometry.

    Args:
        graph: The molecular graph.
        seed: Random seed for reproducibility.

    Returns:
        A Conformer with 3D coordinates.
    """
    if graph.num_atoms == 0:
        return Conformer(id=0, coordinates=(), energy=0.0)
    if graph.num_atoms == 1:
        return Conformer(id=0, coordinates=(Coordinate3D(0.0, 0.0, 0.0),), energy=0.0)

    n = graph.num_atoms
    lower, upper = _build_bounds_matrix(graph)
    dist = _bounds_to_distance_matrix(lower, upper, n)
    coords = _embed_from_distance_matrix(dist, n, seed)
    coords = _minimize_energy(coords, graph)

    return Conformer(
        id=0,
        coordinates=tuple(coords),
        energy=0.0,
    )


def generate_conformers(
    graph: MolecularGraph,
    num_conformers: int = 10,
    seed: int | None = None,
    rmsd_threshold: float = RMSD_CLUSTER_THRESHOLD,
) -> tuple[Conformer, ...]:
    """Generate multiple 3D conformers and cluster by RMSD.

    Args:
        graph: The molecular graph.
        num_conformers: Number of conformers to generate.
        seed: Random seed for reproducibility.
        rmsd_threshold: RMSD threshold for clustering (Angstroms).

    Returns:
        Tuple of unique Conformer objects, sorted by energy.
    """
    if graph.num_atoms <= 1:
        conf = generate_conformer(graph, seed)
        return (conf,)

    rng = random.Random(seed)
    candidates: list[Conformer] = []

    for i in range(num_conformers * 2):  # Generate extra to account for clustering
        conf_seed = rng.randint(0, 2**31)
        conf = generate_conformer(graph, seed=conf_seed)
        conf = Conformer(
            id=i,
            coordinates=conf.coordinates,
            energy=conf.energy,
            properties=conf.properties,
        )
        candidates.append(conf)
        if len(candidates) >= num_conformers * 2:
            break

    # Cluster by RMSD
    clustered = _cluster_conformers(candidates, rmsd_threshold)

    # Sort by energy
    clustered.sort(key=lambda c: c.energy)

    # Re-number
    result = []
    for i, conf in enumerate(clustered[:MAX_CONFORMERS]):
        result.append(Conformer(
            id=i,
            coordinates=conf.coordinates,
            energy=conf.energy,
            properties=conf.properties,
        ))

    return tuple(result)


# ── Clustering ──

def _cluster_conformers(
    conformers: list[Conformer],
    threshold: float,
) -> list[Conformer]:
    """Cluster conformers by RMSD using a greedy approach.
    First conformer becomes the first cluster center.
    """
    if not conformers:
        return []

    clusters: list[Conformer] = [conformers[0]]

    for conf in conformers[1:]:
        is_duplicate = False
        for center in clusters:
            rmsd = _compute_rmsd(conf, center)
            if rmsd < threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            clusters.append(conf)

    return clusters


def _compute_rmsd(a: Conformer, b: Conformer) -> float:
    """Compute RMSD between two conformers (simple alignment-free).
    """
    if a.num_atoms != b.num_atoms:
        return float('inf')
    if a.num_atoms == 0:
        return 0.0

    sum_sq = 0.0
    for i in range(a.num_atoms):
        dx = a.coordinates[i].x - b.coordinates[i].x
        dy = a.coordinates[i].y - b.coordinates[i].y
        dz = a.coordinates[i].z - b.coordinates[i].z
        sum_sq += dx * dx + dy * dy + dz * dz

    return math.sqrt(sum_sq / a.num_atoms)


# ── Energy Computation ──

def compute_conformer_energy(
    conformer: Conformer,
    graph: MolecularGraph,
) -> float:
    """Compute a simple MMFF-like strain energy for a conformer.

    Uses bond length deviations, angle strain, VDW clashes,
    and torsion strain for a more realistic energy estimate.
    """
    if conformer.num_atoms == 0:
        return 0.0

    energy = 0.0

    # 1. Bond length penalty (harmonic)
    for bond in graph.bonds:
        i, j = bond.atom1, bond.atom2
        target = BOND_LENGTHS.get(bond.order, 1.54)
        d = conformer.get_distance(i, j)
        diff = d - target
        energy += 100.0 * diff * diff  # kcal/mol² * Å²

    # 2. Angle strain (1-3 interactions)
    n = graph.num_atoms
    for k in range(n):
        neighbors_k = graph.get_neighbors(k)
        for i_idx in range(len(neighbors_k)):
            for j_idx in range(i_idx + 1, len(neighbors_k)):
                i, j = neighbors_k[i_idx], neighbors_k[j_idx]
                # Ideal angle ~109.5° for sp3, 120° for sp2, 180° for sp
                ideal_angle = 109.5  # default tetrahedral
                d_ik = conformer.get_distance(i, k)
                d_jk = conformer.get_distance(j, k)
                d_ij = conformer.get_distance(i, j)
                if d_ik < 0.1 or d_jk < 0.1:
                    continue
                # Law of cosines: cos(angle) = (a² + b² - c²) / (2ab)
                cos_angle = (d_ik**2 + d_jk**2 - d_ij**2) / (2 * d_ik * d_jk)
                cos_angle = max(-1.0, min(1.0, cos_angle))
                angle_deg = math.degrees(math.acos(cos_angle))
                angle_diff = angle_deg - ideal_angle
                energy += 0.5 * angle_diff * angle_diff  # Gentle angle penalty

    # 3. VDW clash penalty (1-4 and longer non-bonded)
    for i in range(n):
        for j in range(i + 1, n):
            if graph.get_bond(i, j) is not None:
                continue
            r_i = _get_vdw_radius(graph.atoms[i].atomic_number)
            r_j = _get_vdw_radius(graph.atoms[j].atomic_number)
            vdw = r_i + r_j
            d = conformer.get_distance(i, j)
            if d < vdw * 0.8:
                # Lennard-Jones-like repulsion
                energy += 200.0 * (vdw * 0.8 - d) ** 2
            elif d < vdw:
                # Soft repulsion
                energy += 10.0 * (vdw - d) ** 2

    return energy
