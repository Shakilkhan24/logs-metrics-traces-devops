-- A separate monitoring login; no access to ShopSphere table contents.
-- Rerunnable on an existing data volume. Password is for this local lab only.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'shopsphere_metrics') THEN
        CREATE ROLE shopsphere_metrics LOGIN PASSWORD 'metrics_local';
    END IF;
END
$$;
GRANT pg_monitor TO shopsphere_metrics;
GRANT CONNECT ON DATABASE shopsphere TO shopsphere_metrics;
