# Retention and disposal policy

Development and verification records are retained only for the active evidence cycle. The local SQLite database may be reset to the deterministic fictional seed between runs. Screenshots and browser traces must contain fictional seed data only and should be removed when their evidence cycle closes.

Clinical records and audit events have no universal retention period. Before production, the controller must configure an approved jurisdiction- and record-class schedule, legal holds, disposal evidence, backup expiry, export, correction, and access processes. Audit immutability must not be mistaken for indefinite lawful retention.
