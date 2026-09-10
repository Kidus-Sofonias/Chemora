"""Validation report data models.

Defines the structured types used throughout the validation subsystem:
    - ValidationSeverity: Error, warning, or info severity levels.
    - ValidationError: A single validation finding with context.
    - ValidationResult: Aggregated validation outcome.
    - ValidationReport: Complete validation report for a molecule.
    - ValidationRule: Protocol for pluggable validation rules.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from chemengine.core.enums import StrEnum


class ValidationSeverity(StrEnum):
    """Severity level of a validation finding."""

    ERROR = "error"
    """Critical: molecule is chemically invalid."""
    WARNING = "warning"
    """Concerning: molecule may be unusual or unstable."""
    INFO = "info"
    """Informational: observation without chemical concern."""


@dataclass(frozen=True, slots=True)
class ValidationError:
    """A single validation finding with context.

    Attributes:
        rule: Name of the rule that produced this finding (e.g., 'valence', 'charge').
        severity: Severity level (error, warning, info).
        message: Human-readable description of the issue.
        atom_index: Optional index of the atom involved.
        bond_index: Optional index of the bond involved.
        detail: Optional structured detail (e.g., actual vs. expected values).
    """

    rule: str
    severity: ValidationSeverity
    message: str
    atom_index: int | None = None
    bond_index: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Aggregated validation outcome for a set of rules.

    Attributes:
        passed: Whether all rules passed (no errors).
        errors: Tuple of error-severity findings.
        warnings: Tuple of warning-severity findings.
        info: Tuple of info-severity findings.
    """

    passed: bool
    errors: tuple[ValidationError, ...]
    warnings: tuple[ValidationError, ...]
    info: tuple[ValidationError, ...]

    @property
    def is_valid(self) -> bool:
        """Whether the molecule is chemically valid (no errors)."""
        return len(self.errors) == 0

    @property
    def all_findings(self) -> tuple[ValidationError, ...]:
        """Return all findings sorted by severity."""
        return self.errors + self.warnings + self.info

    @property
    def num_errors(self) -> int:
        return len(self.errors)

    @property
    def num_warnings(self) -> int:
        return len(self.warnings)

    @property
    def num_info(self) -> int:
        return len(self.info)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for API output."""
        return {
            "is_valid": self.is_valid,
            "num_errors": self.num_errors,
            "num_warnings": self.num_warnings,
            "num_info": self.num_info,
            "errors": [
                {
                    "rule": e.rule,
                    "severity": e.severity,
                    "message": e.message,
                    "atom_index": e.atom_index,
                    "bond_index": e.bond_index,
                    "detail": dict(e.detail),
                }
                for e in self.errors
            ],
            "warnings": [
                {
                    "rule": w.rule,
                    "severity": w.severity,
                    "message": w.message,
                    "atom_index": w.atom_index,
                    "bond_index": w.bond_index,
                    "detail": dict(w.detail),
                }
                for w in self.warnings
            ],
            "info": [
                {
                    "rule": i.rule,
                    "severity": i.severity,
                    "message": i.message,
                    "atom_index": i.atom_index,
                    "bond_index": i.bond_index,
                    "detail": dict(i.detail),
                }
                for i in self.info
            ],
        }


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Complete validation report for a molecule.

    Attributes:
        molecule_id: Identifier for the molecule (name, SMILES, or formula).
        timestamp: When the validation was performed.
        rule_set: Name of the rule set used ('strict', 'standard', 'relaxed').
        result: The aggregated validation result.
    """

    molecule_id: str
    timestamp: datetime.datetime
    rule_set: str
    result: ValidationResult

    @property
    def is_valid(self) -> bool:
        return self.result.is_valid

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for API output."""
        return {
            "molecule_id": self.molecule_id,
            "timestamp": self.timestamp.isoformat(),
            "rule_set": self.rule_set,
            "is_valid": self.is_valid,
            **self.result.to_dict(),
        }


class ValidationRule(Protocol):
    """Protocol for pluggable validation rules.

    All validation rules must implement this protocol to be registered
    with the ValidationRuleSet and AlgorithmRegistry.

    Usage:
        >>> class MyRule:
        ...     name = "my_rule"
        ...     description = "Checks something specific"
        ...     def validate(self, graph):
        ...         yield ValidationError(...)
    """

    name: str
    """Unique name for this rule (snake_case)."""
    description: str
    """Human-readable description of what this rule checks."""

    def validate(self, graph: Any) -> Iterator[ValidationError]:
        """Run this rule against a molecular graph.

        Args:
            graph: The MolecularGraph to validate.

        Yields:
            ValidationError for each finding.
        """
        ...
        return
        yield  # Make the generator valid even if empty
