# Security Platform Overview

## Source

- Client: Department procurement panel
- Submission year: 2025
- Domain: Security

## Approved Positioning

### Encryption in transit

Our production platform enforces TLS 1.2 or higher for all external service endpoints. Where customers require stronger cipher restrictions, TLS 1.3 can be enabled in supported environments.

Legacy SSL is not enabled for public production traffic. In rare migration projects we may assist a customer to ingest data from a legacy source system through a tightly controlled transition pathway, but this is isolated from public application access.

### Identity and access

The platform supports SAML 2.0 and OpenID Connect based single sign-on. Role-based access control is available at tenant, workspace, and feature level, with least-privilege administrative delegation.

### Logging and traceability

Application and administrative audit logs are retained for at least 365 days in the standard regulated deployment profile. Export to a customer SIEM is supported where required.

### Vulnerability management

Independent penetration testing is performed at least annually and after material architectural change. Critical findings are triaged immediately and remediated under a tracked security process.
