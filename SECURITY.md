# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Doramagic, please report it responsibly.

**Email:** security@doramagic.dev

We will acknowledge receipt within 48 hours and provide an update within 7 days.

## Scope

Doramagic is an OpenClaw skill that reads local knowledge files and generates tool specifications. In its default mode (`/dora`), it:

- Does **not** execute any shell commands or scripts
- Does **not** access the network
- Only reads files within its own skill directory
- Writes output to `~/clawd/doramagic/generated/`

The advanced mode (`/dora-extract`) requires exec approval and may access GitHub APIs.

## API Keys

API keys are read from environment variables and never stored in output files.
The `models.json.example` file contains no real credentials — copy it to `models.json` and add your own keys.
