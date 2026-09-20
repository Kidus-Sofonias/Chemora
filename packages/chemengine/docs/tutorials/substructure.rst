Substructure search
===================

Substructure matching answers "does molecule X contain pattern Y?" — the
core query behind functional-group alerts, scaffold analysis, and filters.

The matcher
-----------

:mod:`chemengine.detection.substructure` provides
:func:`~chemengine.detection.substructure.has_subgraph_match`,
:func:`~chemengine.detection.substructure.find_subgraph_matches`, and
:func:`~chemengine.detection.substructure.count_subgraph_matches`.

Important semantics: matching maps the **full** query graph onto the
**full** target graph. Because parsed SMILES carry explicit hydrogens,
pattern queries are built heavy-atom-only — hydrogens are implied by the
pattern's valences.

A worked example
----------------

.. literalinclude:: ../../examples/03_substructure_search.py

Custom compatibility
--------------------

Both ``find_subgraph_matches`` and ``has_subgraph_match`` accept
``atom_compatible`` and ``bond_compatible`` callables for non-default
matching (e.g., ignoring aromaticity, or matching element classes)::

   find_subgraph_matches(
       target, query,
       atom_compatible=lambda target, t_i, query, q_i: True,  # match anything
   )

The default compatibility rule: same atomic number, query aromaticity
respected, wildcard (atomic number 0) matches any atom; same bond order,
wildcard bond (order 0) matches any bond.

Higher-level alternative
------------------------

For named functional groups (Alcohol, Amide, Carboxylic Acid, ...) use
:meth:`~chemengine.core.tool_interface.ChemEngineAPI.detect_functional_groups`,
which runs curated SMARTS patterns — see the
:doc:`properties` tutorial and ``examples/06_functional_groups.py``.
