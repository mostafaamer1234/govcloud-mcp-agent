# Zero-egress networking

## What zero egress means
A zero-egress workload has no route to the public internet. In AWS GovCloud this is achieved by placing workloads in private subnets with no internet gateway and no NAT gateway, so outbound traffic can only reach destinations inside the VPC.

## Reaching AWS services without the internet
Services such as S3, KMS, Secrets Manager, CloudWatch Logs and Bedrock are reached through VPC endpoints (AWS PrivateLink or gateway endpoints). Endpoint policies restrict which principals and resources each endpoint can be used for.

## Defense in depth inside the application
Network controls can be misconfigured, so the application should also refuse outbound connections it does not expect. An in-process allowlist that checks every socket connect turns an accidental or prompt-injected outbound call into a logged, blocked event instead of a data leak.

## Model hosting under zero egress
Language models must run inside the boundary: a self-hosted model on private compute, or a managed model service reached through a VPC endpoint. Prompts and retrieved documents must never be sent to a public API.
