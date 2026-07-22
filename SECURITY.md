# Security policy

## Reporting a vulnerability

Do not open a public issue.

Report it privately through GitHub:

**[Report a vulnerability](https://github.com/noluyorAbi/printed-business-card/security/advisories/new)**

That form is private between you and the maintainer. It creates a draft
security advisory where the fix can be discussed, and where you are credited by
name when it is published, unless you ask not to be.

## Scope

This repository contains a Python script that generates 3D-printable geometry
files locally. It runs no server, takes no network input, and handles no
credentials. Relevant reports are therefore mostly about the generated 3MF/STL
files (for example crafted inputs producing malformed archives) or about the
dependency chain in `requirements.txt`.

## Response time

Expect a first response within 14 days.
