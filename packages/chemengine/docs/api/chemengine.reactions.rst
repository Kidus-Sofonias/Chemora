Reactions — reaction models, mapping, validation, and mechanism engine
============================================================================

``chemengine.reactions``
------------------------

.. automodule:: chemengine.reactions
   :members:
   :show-inheritance:
   :no-index:

``chemengine.reactions.reaction``
---------------------------------

.. automodule:: chemengine.reactions.reaction
   :members:
   :show-inheritance:
   :no-index:

``chemengine.reactions.mapping``
--------------------------------

Deterministic skeleton-based atom-atom mapping (M33, roadmap 12.2).

.. automodule:: chemengine.reactions.mapping
   :members:
   :show-inheritance:
   :no-index:

``chemengine.reactions.mechanisms``
-----------------------------------

Frozen mechanism architecture interfaces (M33, roadmap 12.5), implemented by
the M34 executable engine.

.. automodule:: chemengine.reactions.mechanisms
   :members:
   :show-inheritance:
   :no-index:

``chemengine.reactions.engine``
--------------------------------

Executable bounded mechanism engine (M34): 10 curated named mechanisms,
12 elementary rules, deterministic validated traces, and structured errors.

.. code-block:: python

   from chemengine.parsing.smiles import parse_smiles
   from chemengine.reactions.engine import MechanismEngine, MechanismScenario
   from chemengine.reactions.reaction import Reaction, ReactionComponent

   reactant = parse_smiles("C[Cl].[OH-]")
   product = parse_smiles("C[O][H].[Cl-]")
   scenario = MechanismScenario(
       name="sn2",
       steps=(Reaction((ReactionComponent(reactant),),
                      (ReactionComponent(product),)),),
   )
   result = MechanismEngine().explain(scenario)
   print(result.rule_names)  # ('sn2',)

.. automodule:: chemengine.reactions.engine
   :members:
   :show-inheritance:
   :no-index:
