# PostgreSQL

Phase 3 will introduce persistent product and order data, SQLAlchemy connections,
and `init.sql` where needed for database initialization. Database configuration
will enable connection, slow-query, and error logging for the exercises.

Later phases will collect database logs and expose database metrics through an
exporter. SQL client spans will come from application instrumentation.

This directory holds versioned configuration, not database data files. Runtime
data will use persistent storage when Compose is added. Production databases
also require backup, recovery, access control, and capacity planning.
