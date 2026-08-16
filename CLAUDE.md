# Instructions for AI Assistants (Claude Code, Cursor, etc.)

You are working on a DGX Spark AI server. 
- Read `ARCHITECTURE.md` before making any changes.
- This is a Docker Compose based project. All services live in the `compose/` directory.
- Never expose ports publicly. All external access goes through Caddy on port 443 (Tailscale interface only).
- When writing Python agents, ensure they are containerized via the `agents/Dockerfile`.
- The user prefers simple, boring, well-documented infrastructure. No Kubernetes.
- If you are unsure if a change will break the 128GB memory limit, ask the user first.
