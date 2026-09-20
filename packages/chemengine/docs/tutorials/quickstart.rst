Quickstart
==========

Install ChemEngine and take the facade for a spin.

.. code-block:: console

   pip install chemengine

Your first molecule
-------------------

Everything goes through :class:`~chemengine.core.tool_interface.ChemEngineAPI`:

.. literalinclude:: ../../examples/01_quickstart.py

Run it yourself:

.. code-block:: console

   python examples/01_quickstart.py

Expected output (values are deterministic — identical on every machine):

.. code-block:: text

   formula:  C6H6
   weight:   78.114
   rings:    1
   InChIKey: 66B07AD6D0CCB2-AD827355BC-A

.. note::

   ``convert(mol, "inchikey")`` produces a deterministic InChIKey-*style*
   hash (SHA-256 of the InChI string) — not the standard InChIKey
   algorithm, which requires the official InChI binaries. See
   :func:`~chemengine.parsing.inchi_serializer.generate_inchi_key`.

What happened
-------------

1. ``parse()`` detected SMILES and built a :class:`~chemengine.core.graph.MolecularGraph`
   — the single source of truth for everything downstream.
2. ``convert()`` and ``compute()`` derive identifiers and properties from
   that graph; nothing is cached or recomputed behind your back.
3. Every operation is deterministic: same graph in, same result out.
