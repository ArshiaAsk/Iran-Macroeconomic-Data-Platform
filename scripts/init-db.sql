-- Initialize TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create schemas for different data layers
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS metadata;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA bronze TO iran_macro;
GRANT ALL PRIVILEGES ON SCHEMA silver TO iran_macro;
GRANT ALL PRIVILEGES ON SCHEMA gold TO iran_macro;
GRANT ALL PRIVILEGES ON SCHEMA metadata TO iran_macro;
