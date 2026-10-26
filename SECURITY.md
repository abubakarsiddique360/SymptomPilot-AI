# Security policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | ✅        |

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's private
reporting:

1. Go to the repository's **Security** tab.
2. Choose **Report a vulnerability** (private advisory).
3. Describe the impact, the steps to reproduce, and any suggested fix.

You can expect an acknowledgement within a few days. Please give the maintainer a
reasonable window to ship a fix before publishing details.

## What counts as a security issue here

- Remote code execution, path traversal, or command injection through the API.
- Cross-site scripting in the web UI (for example via a knowledge-base page or a model reply).
- Server-side request forgery via configurable model or embedding endpoints.
- Unauthorised data exposure — including the SQLite index, conversation history, or logs.
- Prompt-injection techniques that make the assistant **lower** an urgency level
  or suppress a red-flag warning. This is treated as a security bug, not a
  content bug: the deterministic screener is supposed to be unreachable by
  generated text.
- Dependency vulnerabilities reachable from the service.

## Out of scope

- Medical accuracy of the educational content in `knowledge/`. That is handled
  as a regular content issue, though safety-relevant errors are prioritised.
- Denial of service from very large request bodies on a self-hosted instance with
  no rate limiting (documented limitation, see below).
- Reports produced by automated scanners without a concrete, reproducible impact.

## Hardening notes for self-hosting

- The service ships **no authentication**. It is designed for `127.0.0.1` or a
  trusted network. Put it behind your own auth proxy before exposing it.
- There is no rate limiting and no request queue; add both at the edge.
- Conversations are not persisted by the server — history is posted by the client
  on each request and is not written to disk. Do not log request bodies if they
  contain health information.
- The SQLite database (`var/symptompilot.db`) contains only knowledge-base text
  and optional embeddings. Back it up or delete it freely; it is rebuilt on start.
- If you configure `SYMPTOMPILOT_OPENAI_BASE_URL` or `SYMPTOMPILOT_OLLAMA_URL`,
  verify the endpoint is one you trust. Prompts and retrieved passages are sent
  there verbatim.
- Keep `.env` out of version control. Only `.env.example` is tracked.

## Data handling

The project never ships real credentials or patient data. If you find any in the
repository or its history, report it privately so it can be removed.
