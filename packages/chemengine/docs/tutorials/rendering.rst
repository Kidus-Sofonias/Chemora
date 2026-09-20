Rendering
=========

ChemEngine depicts molecules as standalone SVG: ring-aware 2D layout,
deterministic coordinates, no external services.

Coordinates and depiction
-------------------------

.. literalinclude:: ../../examples/05_rendering.py

How it fits together
--------------------

1. :func:`~chemengine.coordinates.layout_2d.generate_2d_coordinates`
   assigns a 2D position to every atom. Ring systems are laid out first
   (regular polygons), then chains are extended outward with a
   force-directed refinement. The layout is deterministic: the same graph
   always produces the same coordinates.
2. :meth:`~chemengine.core.tool_interface.ChemEngineAPI.render` draws the
   graph to an SVG string using those coordinates.

Rendering options
-----------------

``render(graph, fmt="svg", **options)`` accepts:

- ``bond_length`` — bond length in SVG units (default 40.0)
- ``show_hydrogens`` — draw explicit hydrogens (default False)
- ``padding`` — canvas padding in SVG units (default 30.0)
- ``title`` — optional caption rendered under the structure

The output is a self-contained ``<svg>...</svg>`` document: safe to embed
in HTML, write to a file, or return from a web API.
