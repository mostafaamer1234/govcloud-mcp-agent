# Mutual TLS and workload identity

## Why mutual TLS
Standard TLS proves the server's identity to the client. Mutual TLS also requires the client to present a certificate signed by a trusted certificate authority, so only enrolled workloads can open a connection at all. Connections without a valid client certificate fail during the TLS handshake, before any application code runs.

## Certificate authority
In AWS the private certificate authority is typically AWS Private CA. Certificates should be short-lived and rotated automatically; private keys stay on the workload and are never committed to source control.

## Enforcing client certificates
A TLS server must be explicitly configured to require client certificates. Many servers only request one, or accept connections without one, unless the verification mode is set to require a certificate. Integration tests should confirm that a client with no certificate, or with a certificate from an untrusted CA, is rejected.

## Combining mTLS with tokens
Mutual TLS authenticates the workload at the transport layer. Bearer tokens with scopes add application-level authorization, so a compromised but enrolled workload still cannot call tools outside its scopes.
