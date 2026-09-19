"""AI Chemistry Tutor service layer (M29).

Exposes the authenticated tutor endpoint, the AI provider abstraction, the
ChemEngine tool-execution boundary, and student-safe content retrieval.

The LLM is an explanation/reasoning surface only. Deterministic chemistry
results always come from ChemEngine through the explicit tool allowlist
defined in :mod:`app.services.ai.tools`.
"""
