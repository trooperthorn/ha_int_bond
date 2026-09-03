# Security Policy

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, private
addresses, or logs. Use GitHub's private vulnerability-reporting feature for
this repository. If private reporting is unavailable, open a minimal issue
asking the maintainer to establish a private channel; omit technical details.

Include the affected version/commit, prerequisites, impact, a minimal
reproduction, and suggested remediation. Remove tokens, API keys, cookies,
camera images, usernames, and private network details.

## Response targets

These are project targets, not an SLA: acknowledge critical/high reports in
three business days, establish severity and containment in seven, and publish
a coordinated fix/advisory as soon as safely validated. Lower-severity issues
are prioritized by exploitability and impact.

## Supported version

Only the latest published release and the default branch receive security
fixes. Operators should update Home Assistant and Bond Pro promptly and
retain a tested rollback/backup.

## Security boundaries

Bond Pro is a privileged Home Assistant integration, not a sandbox or an
independent compliance product. It talks to a Bond Bridge over the local
network using a bearer token stored in the config entry; it has no cloud
dependency. That token grants full local control of the bridge and its paired
devices, so its confidentiality is the primary trust boundary: anyone with
the token can control every device the bridge pairs. The integration cannot
prevent a malicious integration in the same Python process from reading
shared memory or files. Its findings are not a certification or a claim that
no vulnerability exists.
