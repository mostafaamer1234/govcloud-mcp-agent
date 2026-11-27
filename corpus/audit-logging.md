# Audit logging for AI tool calls

## What to record
Every tool decision should be recorded: the calling identity, the tool, whether the call was allowed or denied, latency, and a correlation identifier that ties the record to the request. Arguments can be stored as a hash so the audit trail does not become a second copy of sensitive data.

## Tamper evidence
Chaining each record to the hash of the previous record makes the log tamper-evident: editing or deleting any record breaks every hash that follows. Periodic verification detects the break and identifies the first altered record.

## Shipping and retention
In AWS, audit records are shipped to CloudWatch Logs and archived to S3 with Object Lock for immutable retention. Security teams forward them to a SIEM for alerting on repeated denials or blocked egress attempts.

## Incident response
When an alert fires, responders use the correlation identifier to reconstruct which agent called which tool, with what result, and whether any outbound connection was attempted.
