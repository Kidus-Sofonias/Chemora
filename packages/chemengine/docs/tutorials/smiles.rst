SMILES
======

SMILES is ChemEngine's primary input language. This tutorial covers
parsing, serialization, canonicalization, and the round-trip identity
property that the engine's own property-based tests rely on.

Parsing
-------

.. code-block:: python

   from chemengine.parsing.smiles import parse_smiles

   mol = parse_smiles("CC(=O)Oc1ccccc1C(=O)O")   # aspirin
   print(mol.molecular_formula)                   # C9H8O4

``parse_smiles`` implements the OpenSMILES grammar: atoms, bond orders,
rings, branches, charges, isotopes, and ``@``/``@@`` tetrahedral stereo.
Invalid input raises :class:`~chemengine.parsing.errors.FormulaParseError`
or ``ValueError`` with a structured message — never a silent partial parse.

Serialization and canonicalization
----------------------------------

.. literalinclude:: ../../examples/02_smiles_roundtrip.py

Notes:

- ``serialize_smiles`` writes a deterministic canonical traversal, so the
  same graph always serializes to the same string.
- The canonical form is an equivalence check: two different SMILES spellings
  of one molecule produce identical canonical SMILES.

Round-trip identity
-------------------

For any parseable SMILES ``s``::

   canonical(parse(serialize(parse(s)))) == canonical(parse(s))

This invariant is property-tested (see ``tests/test_property_based.py``)
and holds for every molecule in the test corpus.
