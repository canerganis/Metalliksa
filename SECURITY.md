# Security policy

Metalliksa is a local research workstation. It runs on your machine, stores no accounts and, unless you enable the optional AI features with your own `OPENAI_API_KEY`, makes no outbound calls. An air-gap mode blocks outbound calls entirely.

## Reporting a vulnerability

Please report security issues privately through GitHub: **Security > Report a vulnerability** on this repository (private vulnerability reporting). Do not open a public issue for a vulnerability.

If GitHub reporting is unavailable to you, email muhammetcanerganis@gmail.com instead (do not include exploit details in public places).

Include what you found, how to reproduce it and the affected version or commit. You will get an acknowledgement as soon as the maintainer can respond; this is a single-maintainer project, so please allow some days.

## Scope

In scope: the Express server and its routes, the Python solver bridge, file and archive handling (imports, run bundles) and any path that could read, write or execute outside the project.

Out of scope: scientific accuracy of solver results (use a normal issue; see the evidence statements in the README), and findings that require an attacker who already controls your machine.

## Secrets

Never commit API keys. Use `.env` (ignored by git); `.env.example` lists the variables. If you find a credential in this repository or its history, report it privately as above.
