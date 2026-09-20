# Security Policy

## Supported versions

ChemEngine is released as a versioned package (see
`packages/chemengine/CHANGELOG.md`). Security fixes are applied to the
latest release line only; users should upgrade to the newest version.

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅        |
| < 1.0   | ❌        |

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Report privately via GitHub's "Report a vulnerability" feature on the
repository's Security tab, or contact the maintainer directly
(<kidus.sofonias@example.com>).

Please include:

- A description of the issue and its impact.
- Steps to reproduce (a minimal script is ideal).
- The version of ChemEngine and Python you used.

## Response targets

- Acknowledgement: within 7 days.
- Assessment and severity classification: within 14 days.
- Fix or mitigation for confirmed issues: within 90 days for high
  severity, best-effort for lower severity.

## Scope

ChemEngine is an in-process chemistry library. It performs no networking,
holds no secrets, and executes no untrusted code. Vulnerabilities in scope
include, for example:

- Correctness defects that could produce silently wrong chemistry results
  when used as documented.
- Crashes/memory-safety issues reachable from documented public APIs
  (parsing untrusted identifier strings is the obvious attack surface —
  `parse_smiles`, `parse_inchi`, `parse_formula`, `parse`).
- Anything in the Chemora product deployment that allows a client to
  reach ChemEngine in a way the documentation does not intend.

Out of scope: vulnerabilities in the applications *using* ChemEngine
(backend, web, admin have their own security processes), social
engineering, and issues requiring physical access.

## Safe harbor

We will not pursue legal action against researchers who report issues in
good faith, avoid privacy violations and service degradation, and give us
a reasonable window to respond before public disclosure.
