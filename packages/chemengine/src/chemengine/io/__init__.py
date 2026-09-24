"""IO — Serialization, deserialization, and format conversion.

Modules:
    serialization: JSON/dict serialization for molecular graphs and reactions
"""

from chemengine.io.serialization import (
    MECHANISM_TRACE_SCHEMA,
    convert_format,
    dict_to_graph,
    dict_to_mechanism_trace,
    dict_to_reaction,
    graph_to_dict,
    graph_to_json,
    json_to_graph,
    json_to_mechanism_trace,
    mechanism_trace_to_dict,
    mechanism_trace_to_json,
    reaction_to_dict,
)

__all__ = [
    "graph_to_dict",
    "graph_to_json",
    "dict_to_graph",
    "json_to_graph",
    "convert_format",
    "reaction_to_dict",
    "dict_to_reaction",
    "MECHANISM_TRACE_SCHEMA",
    "mechanism_trace_to_dict",
    "dict_to_mechanism_trace",
    "mechanism_trace_to_json",
    "json_to_mechanism_trace",
]
