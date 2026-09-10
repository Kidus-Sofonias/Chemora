"""Validation subsystem — graph sanitization, valence rules, and molecular validity checks.

Provides:
    - ValidationResult, ValidationError, ValidationReport: structured validation output
    - ValidationRule protocol: extensible rule interface
    - Built-in rules: valence, charge, isotope, graph structure, aromaticity, radicals
    - get_validation_rules(): rule set selection (strict/standard/relaxed)
    - sanitize(): graph repair (add implicit H, remove duplicate bonds)
"""

from __future__ import annotations

from chemengine.validation.report import (
    ValidationError,
    ValidationReport,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
)
from chemengine.validation.rules import (
    AromaticityRule,
    ChargeRule,
    GraphStructureRule,
    HypervalentRule,
    IsotopeRule,
    RadicalRule,
    TotalChargeRule,
    ValenceRule,
    ValenceSaturationRule,
    get_validation_rules,
)
from chemengine.validation.sanitize import (
    add_implicit_hydrogens,
    assign_formal_charges,
    remove_duplicate_bonds,
    sanitize,
)

__all__ = [
    "ValidationError",
    "ValidationResult",
    "ValidationReport",
    "ValidationRule",
    "ValidationSeverity",
    "ValenceRule",
    "HypervalentRule",
    "ChargeRule",
    "TotalChargeRule",
    "IsotopeRule",
    "GraphStructureRule",
    "RadicalRule",
    "ValenceSaturationRule",
    "AromaticityRule",
    "get_validation_rules",
    "add_implicit_hydrogens",
    "assign_formal_charges",
    "remove_duplicate_bonds",
    "sanitize",
]
