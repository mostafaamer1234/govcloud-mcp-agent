# Secrets and key management

## Where secrets live
Application secrets belong in AWS Secrets Manager or SSM Parameter Store, encrypted with customer-managed KMS keys. Workloads read them at runtime through VPC endpoints using IAM roles, never from files committed to source control.

## Keys in git history
Deleting a committed private key in a new commit is not enough: the key remains in the repository history. The history must be rewritten to remove it, and the key must be considered compromised and rotated.

## Token storage
Services that validate static tokens should store only a hash of each token and compare hashes in constant time, so a leaked configuration file does not reveal usable credentials.
