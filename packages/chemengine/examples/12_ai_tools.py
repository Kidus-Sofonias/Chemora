"""12 — AI tools: the self-describing facade for LLM agents.

Every capability is exposed as a named tool with JSON Schema input/output
descriptions, listable via ``list_tools()`` and callable via
``execute_tool()`` — the exact surface the Chemora AI tutor uses.
"""

import json

from chemengine import ChemEngineAPI

chem = ChemEngineAPI()

# 1. Discover the tool surface.
tools = chem.list_tools()
print(f"{len(tools)} tools available:")
for tool in tools:
    print(f"  {tool.name:<30} [{tool.category}]")

# 2. Inspect a tool's contract (what an LLM would receive).
schema = next(t for t in tools if t.name == "parse_smiles")
print("parse_smiles input schema:")
print(json.dumps(schema.input_schema, indent=2)[:220], "...")

# 3. Execute tools (name + JSON parameters, like a function call).
result = chem.execute_tool("parse_smiles", {"smiles": "CCO", "compute": ["weight", "formula"]})
print("parse_smiles ->", {k: result[k] for k in ("formula", "exact_mass")})

props = chem.execute_tool(
    "compute_property",
    {"smiles": "CC(=O)Oc1ccccc1C(=O)O", "properties": ["logp", "tpsa"]},
)
print("compute_property ->", props["properties"])

svg = chem.execute_tool("render_svg", {"smiles": "c1ccccc1"})
print("render_svg ->", f"{len(svg['svg'])} chars of SVG markup")

# 4. Batch execution with correlation IDs for pipeline tracing.
batch = chem.execute_batch([
    ("parse_smiles", {"smiles": "CCO"}, "corr-1"),
    ("parse_smiles", {"smiles": "CCC"}, "corr-2"),
])
print("batch results:", [r["formula"] for r in batch])

assert len(tools) >= 10
assert result["formula"] == "C2H6O"
assert "logp" in props["properties"] and "tpsa" in props["properties"]
assert svg["svg"].startswith("<svg")
print("AI tool surface verified")
