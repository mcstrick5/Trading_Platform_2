const { Client } = require('pg');

// Allow running backend without a DB (CSV-only mode)
if (process.env.SKIP_DB === '1') {
    module.exports = null;
} else {
    const client = new Client({
        host: process.env.POSTGRES_HOST || 'localhost',
        port: process.env.POSTGRES_PORT || 5432,
        database: 'finance_data',
        user: process.env.POSTGRES_USER,
        password: process.env.POSTGRES_PASSWORD
    });

    client.connect().catch(err => {
        console.error('Postgres connection error:', err);
    });

    module.exports = client;
}