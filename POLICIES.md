# Platform Policies

## Data Retention Policy

### Account Data
- **Active Accounts:** Retained indefinitely while account is in use
- **Inactive Accounts:** Deleted after 180 days of inactivity  
- **Deleted Accounts:** Complete data removal within 30 days

### Campaign Data
- **Active Campaigns:** Retained for campaign duration + 90 days
- **Archived Campaigns:** Retained for 1 year
- **Analytics Data:** Aggregated metrics retained for 2 years

### Log Data
- **Application Logs:** Rotated after 50MB, retained for 30 days
- **Security Logs:** Retained for 1 year
- **Audit Logs:** Retained for 3 years for compliance

### Backups
- **Full Backups:** Weekly, retained for 4 weeks
- **Incremental Backups:** Daily, retained for 7 days
- **Disaster Recovery Backups:** Monthly, retained for 1 year

## GDPR Compliance

### Data Subject Rights
- **Right to Access:** Users can request all stored data
- **Right to Rectification:** Users can correct inaccurate data
- **Right to Erasure:** Users can request complete deletion
- **Right to Portability:** Data exported in JSON format
- **Right to Object:** Users can opt-out of processing

### Legal Basis
- **Contract Performance:** Account management and service delivery
- **Legitimate Interest:** Fraud prevention, security
- **Consent:** Marketing communications (opt-in)

### Data Processing
- **Purpose Limitation:** Data used only for stated purposes
- **Data Minimization:** Only necessary data collected
- **Storage Limitation:** Retention periods enforced
- **Integrity:** Encryption at rest and in transit
- **Confidentiality:** Access controls and audit logging

### International Transfers
- Data stored within EU/EEA
- Standard Contractual Clauses for third-party services
- Privacy Shield compliance where applicable

##Terms of Service

### Acceptable Use
- **Permitted:** Legitimate marketing, customer engagement
- **Prohibited:** Spam, harassment, illegal content, ToS violations

### Account Termination
- Immediate termination for illegal activity
- Warning + suspension for policy violations
- Data export provided before deletion

### Service Availability
- **Target Uptime:** 99.5%
- **Maintenance Windows:** Announced 48 hours in advance
- **SLA Credits:** Available for enterprise plans

### Liability
- Service provided "as is"
- No liability for account bans from Telegram
- Maximum liability limited to fees paid

## Privacy Policy

### Information Collection
- **Account Data:** Phone numbers, usernames (encrypted)
- **Usage Data:** Campaign metrics, delivery stats
- **Technical Data:** IP addresses (hashed), session data (encrypted)

### Information Use
- Service delivery and improvement
- Security and fraud prevention  
- Legal compliance

### Information Sharing
- **Third Parties:** SMS providers (minimal data)
- **Legal Requirements:** Law enforcement requests
- **No Sale:** User data never sold

### Security Measures
- End-to-end encryption for sensitive data
- Fernet encryption for stored credentials
- TLS 1.2+ for data in transit
- Regular security audits

### Cookie Policy
- Essential cookies only (authentication)
- No tracking or analytics cookies
- Session cookies expire after 24 hours

## Incident Response Procedures

### Severity Levels

**P1 - Critical**
- System-wide outage
- Data breach
- Security compromise
- Response time: 15 minutes

**P2 - High**
- Service degradation
- Feature outage
- Response time: 1 hour

**P3 - Medium**
- Minor bugs
- Performance issues
- Response time: 4 hours

**P4 - Low**
- Cosmetic issues
- Enhancement requests
- Response time: 1 business day

### Response Workflow

1. **Detection:** Monitoring alerts or user reports
2. **Triage:** Assess severity and impact
3. **Communication:** Notify stakeholders
4. **Investigation:** Root cause analysis
5. **Mitigation:** Implement fix or workaround
6. **Resolution:** Verify fix in production
7. **Post-Mortem:** Document lessons learned

### Security Incident Response

1. **Containment:** Isolate affected systems
2. **Evidence:** Preserve logs and artifacts
3. **Eradication:** Remove threat
4. **Recovery:** Restore service
5. **Notification:** Inform affected users within 72 hours (GDPR)
6. **Review:** Update security measures

## Service Level Agreement (SLA)

### Availability Targets
- **Production:** 99.5% uptime (monthly)
- **Planned Maintenance:** Max 4 hours/month
- **Unplanned Downtime:** Max 3.6 hours/month

### Performance Targets
- **API Response Time:** < 200ms (95th percentile)
- **Campaign Start:** < 5 minutes
- **Health Check:** < 50ms

### Support Response Times
- **Enterprise:** 24/7 support, 15-minute response
- **Business:** Business hours, 1-hour response
- **Standard:** Best effort, 1-business day

### SLA Credits
- 99.0-99.5%: 10% credit
- 95.0-99.0%: 25% credit
- < 95.0%: 50% credit

## Capacity Planning

### Resource Allocation
- **CPU:** 2 cores base, auto-scale to 8
- **Memory:** 2GB base, auto-scale to 8GB
- **Storage:** 10GB base, expandable to 1TB
- **Network:** 1Gbps

### Scaling Triggers
- CPU > 70% for 5 minutes
- Memory > 80% for 5 minutes
- Request queue > 100 for 2 minutes

### Growth Projections
- 50% YoY user growth
- 100% YoY data growth
- Quarterly capacity reviews

## Disaster Recovery Plan

### Recovery Objectives
- **RTO (Recovery Time):** 4 hours
- **RPO (Recovery Point):** 1 hour
- **Data Loss Tolerance:** Maximum 1 hour of data

### Backup Strategy
- **Full Backup:** Weekly (Sunday 00:00 UTC)
- **Incremental:** Daily (01:00 UTC)
- **Real-time Replication:** Critical databases

### Recovery Procedures
1. Declare disaster
2. Activate DR team
3. Restore from backup
4. Verify data integrity
5. Switch DNS to DR site
6. Monitor and validate
7. Document incident

### Testing Schedule
- **Backup Verification:** Monthly
- **DR Drill:** Quarterly
- **Full Failover Test:** Annually

