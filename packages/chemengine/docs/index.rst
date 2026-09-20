Getting Started
===============

ChemEngine is a production-grade chemistry engine built around a single
principle: **the molecular graph is the single source of truth**. Every
atom, bond, charge, isotope, stereocenter, coordinate, and property derives
from that graph.

Installation
------------

.. code-block:: console

   pip install chemengine

For development (tests, docs, type checking):

.. code-block:: console

   pip install -e "chemengine[dev]"

Quickstart
----------

The :class:`~chemengine.core.tool_interface.ChemEngineAPI` facade is the
single entry point for all capabilities:

.. code-block:: python

   from chemengine import ChemEngineAPI

   chem = ChemEngineAPI()
   mol = chem.parse("CC(=O)Oc1ccccc1C(=O)O")   # aspirin from SMILES
   print(chem.convert(mol, "formula"))          # C9H8O4
   print(chem.compute(mol, "weight"))           # 180.158...
   print(chem.detect_functional_groups(mol)[0]["name"])

For LLM/AI agents, the facade is self-describing:

.. code-block:: python

   tools = chem.list_tools()                    # JSON-Schema'd tool list
   result = chem.execute_tool("parse_smiles", {"smiles": "CCO"})

Tutorials
---------

The roadmap tutorials live in :doc:`tutorials/index` and the runnable
scripts under ``examples/`` in the repository.

API Reference
-------------

.. toctree::
   :maxdepth: 2

   tutorials/index
   api/index

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
