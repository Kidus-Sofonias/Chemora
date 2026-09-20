AI / tool integration
=====================

ChemEngine is designed to be the deterministic chemistry authority behind
LLM agents. The facade exposes every capability as a **self-describing
tool**: a name, a description, and JSON Schema input/output contracts that
an agent can discover and call.

The tool surface
----------------

.. literalinclude:: ../../examples/12_ai_tools.py

How agents use it
-----------------

1. **Discover** — call ``list_tools()`` and hand the tool definitions to
   the LLM as its function-calling menu (each
   :class:`~chemengine.core.tool_interface.ToolDefinition` already carries
   JSON Schemas).
2. **Dispatch** — when the model selects a tool, call
   ``execute_tool(name, params)``. The facade validates and executes, and
   returns JSON-serializable output.
3. **Trace** — pass a correlation id as the third element of an
   ``execute_batch`` call to trace a multi-step pipeline through the event
   bus.

Why a tool allowlist matters
----------------------------

``execute_tool`` only dispatches the registered, schema-validated tools —
there is no path from model output to arbitrary Python execution. This is
the property that lets the Chemora backend hand the engine to an LLM with
an explicit allowlist on top (see the Chemora M29/M30 architecture).

Designing your own tools
------------------------

Register additional tools on the facade's registry to expose custom
algorithms with the same schema contract::

   from chemengine.core.tool_interface import ToolDefinition

   chem.registry.register(
       "my_domain", "my_tool",
       algorithm=my_function,              # callable(dict) -> JSON-ready value
       tool=ToolDefinition(
           name="my_tool",
           description="Does something domain-specific",
           input_schema={"type": "object", "properties": {}},
           output_schema={"type": "object", "properties": {}},
           category="custom",
       ),
   )
