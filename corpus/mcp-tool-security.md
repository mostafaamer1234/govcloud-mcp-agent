# Securing MCP tool servers

## Least privilege for agents
Each agent should receive only the scopes it needs. A research agent may search and answer from documents, while only an auditor identity may read audit status. Tools that are not listed in the authorization policy are denied by default.

## Prompt injection and tool misuse
Retrieved documents can contain instructions written by an attacker. Tool servers must treat model-generated tool arguments as untrusted input, validate them against a schema, bound sizes such as result counts, and never grant extra privileges because a prompt asks for them.

## Grounded answers
Answers should be built only from retrieved passages and cite the passage each claim comes from. A verifier can reject answers that cite sources that were never retrieved or that contain no citations at all.

## Transport protections
Streamable HTTP endpoints should validate the Host header to prevent DNS rebinding, require authentication on every request, and limit request body sizes.
