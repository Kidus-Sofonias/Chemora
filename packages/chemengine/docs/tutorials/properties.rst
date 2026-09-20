Properties
==========

ChemEngine computes molecular descriptors deterministically from the
molecular graph — no learned models, no approximations beyond the
documented algorithms (Wildman-Crippen logP, Ertl TPSA).

The descriptor panel
--------------------

.. literalinclude:: ../../examples/04_properties.py

Supported properties via the facade
-----------------------------------

:meth:`~chemengine.core.tool_interface.ChemEngineAPI.compute` accepts:

===================  =====================================================
Name                 Meaning
===================  =====================================================
``mass``             exact monoisotopic mass (float)
``weight``           average molecular weight (float)
``formula``          Hill-system molecular formula (str)
``heavy_atoms``      non-hydrogen atom count (int)
``logp``             Wildman-Crippen logP (float)
``tpsa``             topological polar surface area (float)
``fraction_csp3``    fraction of sp3 carbons (float)
``hba``              H-bond acceptor count (int)
``hbd``              H-bond donor count (int)
``rotatable_bonds``  rotatable bond count (int)
``num_rings``        ring count (int)
===================  =====================================================

Unknown names raise ``ValueError`` listing every supported property.

Lipinski-style filtering
------------------------

Combine descriptors into drug-likeness filters::

   from chemengine.parsing.smiles import parse_smiles
   from chemengine.properties.descriptors import compute_hbd, compute_logp, compute_tpsa

   def lipinski_pass(smiles: str) -> bool:
       mol = parse_smiles(smiles)
       return compute_logp(mol) < 5 and compute_tpsa(mol) < 140 and compute_hbd(mol) <= 5

All values are exact functions of the graph: the same molecule yields the
same numbers in every process, on every platform.
