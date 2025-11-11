const psqlClient = require("../models/data.server.model.js");
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { spawn } = require('child_process');

async function marketExists(symbol, exchange) {
    const query = "SELECT * FROM markets WHERE symbol = $1 AND exchange = $2";
    const values = [symbol, exchange];
    const result = await psqlClient.query(query, values);
  return result.rows.length > 0;
}

exports.insertMarket = async function (req, res) {
    if (!req.body.symbol || !req.body.exchange) {
        res.status(400).send({error: "Missing required fields"});
        return;
    }
    let exists = await marketExists(req.body.symbol, req.body.exchange);

    if (exists) {
        res.status(400).send({error: "Market already exists"});
        return;
    }

    const query = "INSERT INTO markets (symbol, exchange, market_type, min_move) VALUES ($1, $2, $3, $4) RETURNING *";
    const values = [req.body.symbol, req.body.exchange, req.body.marketType, req.body.minMove];
    psqlClient.query(query, values, (err, result) => {
        if (err) {
            console.log(err);
            res.status(500).send;
        }
        res.status(201).json(result.rows[0]);
    });
}

exports.getMarkets = function (req, res) {
    const query = "SELECT * FROM markets";
    psqlClient.query(query, (err, result) => {
        if (err) {
            console.log(err);
            res.status(500).send;
        }
        res.status(200).json(result.rows);
    });
};

// NEW: Trigger incremental CSV refresh for all symbols/timeframes in data dir
// Route: POST /api/csv-refresh
exports.csvRefresh = async function (req, res) {
    try {
        const projectRoot = path.resolve(__dirname, '../../../..');
        const pyExe = process.env.PYTHON_EXE || path.join(projectRoot, 'venv', 'Scripts', 'python.exe');
        const helperPath = path.join(projectRoot, 'algotrader', 'tools', 'csv_incremental_update.py');
        const dataDir = process.env.MT5_DATA_DIR || path.resolve(projectRoot, 'mt5_data', 'mt5_csv');

        if (!fs.existsSync(helperPath)) {
            return res.status(500).json({ error: `Updater not found: ${helperPath}` });
        }

        const env = { ...process.env, MT5_DATA_DIR: dataDir };
        const args = [helperPath];
        const child = spawn(pyExe, args, { env });
        let stdout = '';
        let stderr = '';
        child.stdout.on('data', (d) => { stdout += d.toString(); });
        child.stderr.on('data', (d) => { stderr += d.toString(); });
        child.on('close', (code) => {
            if (code !== 0) {
                console.error('csv_refresh error:', stderr || `exit ${code}`);
                return res.status(500).json({ error: 'CSV refresh failed', detail: stderr || `exit ${code}` });
            }
            try {
                const parsed = JSON.parse(stdout || '{}');
                return res.json(parsed);
            } catch (e) {
                // If helper printed plain text, return it raw
                return res.json({ output: stdout });
            }
        });
    } catch (err) {
        console.error('csvRefresh error:', err);
        return res.status(500).json({ error: 'Failed to start CSV refresh' });
    }
};

// NEW: Compute indicators from CSV using Python helper
// Route: GET /api/csv-indicator/:symbol?timeframe=D1&name=RSI&params={...}
exports.getCsvIndicator = async function (req, res) {
    try {
        const symbol = req.params.symbol;
        const timeframe = req.query.timeframe;
        const name = req.query.name;
        const params = req.query.params; // JSON string or key=value pairs

        if (!symbol || !timeframe || !name) {
            return res.status(400).json({ error: 'Missing symbol, timeframe, or name' });
        }

        // Resolve python and helper script paths
        const projectRoot = path.resolve(__dirname, '../../../..');
        const pyExe = process.env.PYTHON_EXE || path.join(projectRoot, 'venv', 'Scripts', 'python.exe');
        const helperPath = path.join(projectRoot, 'algotrader', 'tools', 'csv_indicator.py');

        // Ensure files exist
        if (!fs.existsSync(helperPath)) {
            return res.status(500).json({ error: `Helper not found: ${helperPath}` });
        }

        // Build args
        const args = [helperPath, '--symbol', symbol, '--timeframe', String(timeframe), '--name', String(name)];
        const dataDir = process.env.MT5_DATA_DIR || path.resolve(projectRoot, 'mt5_data', 'mt5_csv');
        args.push('--data_dir', dataDir);
        if (params) {
            args.push('--params', String(params));
        }

        const env = { ...process.env, MT5_DATA_DIR: dataDir };

        const child = spawn(pyExe, args, { env });
        let stdout = '';
        let stderr = '';
        child.stdout.on('data', (d) => { stdout += d.toString(); });
        child.stderr.on('data', (d) => { stderr += d.toString(); });
        child.on('close', (code) => {
            if (code !== 0) {
                console.error('csv_indicator error:', stderr || `exit ${code}`);
                return res.status(500).json({ error: 'Indicator computation failed', detail: stderr || `exit ${code}` });
            }
            try {
                const parsed = JSON.parse(stdout || '[]');
                return res.json(parsed);
            } catch (e) {
                console.error('csv_indicator parse error:', e, stdout);
                return res.status(500).json({ error: 'Failed to parse indicator output' });
            }
        });
    } catch (err) {
        console.error('getCsvIndicator error:', err);
        return res.status(500).json({ error: 'Failed to compute indicator' });
    }
};

// NEW: CSV-backed markets for frontend data-accessor API
// Route: GET /api/data-accessor/markets
exports.getCsvMarkets = async function (req, res) {
    try {
        const baseDir = process.env.MT5_DATA_DIR || path.resolve(__dirname, '../../../../mt5_data');
        if (!fs.existsSync(baseDir)) {
            return res.json([]);
        }
        const files = fs.readdirSync(baseDir).filter(f => f.toLowerCase().endsWith('.csv'));
        const symbols = new Set();
        for (const f of files) {
            const name = path.parse(f).name; // SYMBOL_TF
            const idx = name.lastIndexOf('_');
            if (idx > 0) {
                symbols.add(name.substring(0, idx));
            }
        }

        const isForex = (s) => /^[A-Z]{6}$/.test(s);
        const markets = Array.from(symbols).map(sym => ({
            symbol_id: sym, // use symbol text as id for CSV mode
            symbol: sym,
            exchange: 'CSV',
            market_type: 'local',
            // 4 decimals for forex, 2 decimals for others
            min_move: isForex(sym) ? 0.0001 : 0.01,
        }));

        return res.json(markets);
    } catch (err) {
        console.error('getCsvMarkets error:', err);
        return res.status(500).json({ error: 'Failed to list CSV markets' });
    }
};

// Helper: normalize timeframe (accepts names like D1/H12 or minutes like 1440/720)
function normalizeTimeframe(tf) {
    if (!tf) return null;
    const s = String(tf).toUpperCase();
    // Normalize common aliases first
    const alias = {
        'D': 'D1', '1D': 'D1', 'DAILY': 'D1',
        'H12': 'H12', '12H': 'H12',
        'H4': 'H4', '4H': 'H4',
        'H1': 'H1', '1H': 'H1',
        'W': 'W1', '1W': 'W1', 'WEEKLY': 'W1',
        'M': 'MN1', '1M': 'MN1', 'MONTHLY': 'MN1',
        'M30': 'M30', '30M': 'M30',
        'M15': 'M15', '15M': 'M15',
        'M5': 'M5', '5M': 'M5',
        'M1': 'M1', '1MIN': 'M1'
    };
    if (alias[s]) return alias[s];
    // If already a known code, return
    const known = new Set(['M1','M5','M15','M30','H1','H4','H12','D1','W1','MN1']);
    if (known.has(s)) return s;
    // Try numeric minutes
    const minutes = parseInt(s, 10);
    if (!isNaN(minutes)) {
        const map = {
            1: 'M1',
            5: 'M5',
            15: 'M15',
            30: 'M30',
            60: 'H1',
            240: 'H4',
            720: 'H12',
            1440: 'D1',
            10080: 'W1',
            43200: 'MN1',
        };
        return map[minutes] || null;
    }
    return null;
}

// NEW: CSV-backed candles for frontend data-accessor API
// Route: GET /api/data-accessor/candles/:symbol?timeframe=D1 or timeframe=1440
exports.getCsvCandlesByQuery = async function (req, res) {
    try {
        const tf = normalizeTimeframe(req.query.timeframe);
        if (!tf) return res.status(400).json({ error: 'Invalid or missing timeframe' });
        req.params.timeframe = tf;
        return exports.getCsvCandles(req, res);
    } catch (err) {
        console.error('getCsvCandlesByQuery error:', err);
        return res.status(500).json({ error: 'Failed to read CSV candles' });
    }
};

exports.getCandles = async function (req, res) {
    const symbolID = req.params.symbolID;
    const timeframe = req.params.timeframe;
    
    const query = `
        WITH RoundedCandles AS (
            SELECT
                symbol_id,
                -- Convert timestamp to total minutes since the start of the day (hours * 60 + minutes)
                date_trunc('day', timestamp) + INTERVAL '1 minute' * (
                    ((EXTRACT(HOUR FROM timestamp)::integer * 60) + EXTRACT(MINUTE FROM timestamp)::integer) - 
                    ((EXTRACT(HOUR FROM timestamp)::integer * 60 + EXTRACT(MINUTE FROM timestamp)::integer) % $2)
                ) AS rounded_timestamp,
                open,
                high,
                low,
                close,
                volume,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol_id, date_trunc('day', timestamp) + INTERVAL '1 minute' * (
                        ((EXTRACT(HOUR FROM timestamp)::integer * 60) + EXTRACT(MINUTE FROM timestamp)::integer) - 
                        ((EXTRACT(HOUR FROM timestamp)::integer * 60 + EXTRACT(MINUTE FROM timestamp)::integer) % $2)
                    )
                    ORDER BY timestamp ASC
                ) AS rn_asc,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol_id, date_trunc('day', timestamp) + INTERVAL '1 minute' * (
                        ((EXTRACT(HOUR FROM timestamp)::integer * 60) + EXTRACT(MINUTE FROM timestamp)::integer) - 
                        ((EXTRACT(HOUR FROM timestamp)::integer * 60 + EXTRACT(MINUTE FROM timestamp)::integer) % $2)
                    )
                    ORDER BY timestamp DESC
                ) AS rn_desc
            FROM candles
            WHERE symbol_id = $1
        )
        SELECT
            symbol_id,
            rounded_timestamp AS timestamp,
            MAX(open) FILTER (WHERE rn_asc = 1) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            MAX(close) FILTER (WHERE rn_desc = 1) AS close,
            SUM(volume) AS volume
        FROM RoundedCandles
        GROUP BY symbol_id, timestamp
        ORDER BY timestamp;
    `;
    const result = await psqlClient.query(query, [symbolID, timeframe]);

    res.json(result.rows);
};

// NEW: Serve candles directly from CSV files saved by MT5 downloader
// Route: GET /api/csv-candles/:symbol/:timeframe  (accepts D1/H12 or minutes like 1440/720)
exports.getCsvCandles = async function (req, res) {
    try {
        const symbol = req.params.symbol;
        const timeframe = normalizeTimeframe(req.params.timeframe);
        if (!timeframe) return res.status(400).json({ error: 'Invalid or missing timeframe' });

        // Allow overriding CSV dir via env; default to projectRoot/mt5_data
        const baseDir = process.env.MT5_DATA_DIR || path.resolve(__dirname, '../../../../mt5_data');
        // Build primary and fallback filenames (handle aliases like D -> D1, 12H -> H12)
        const primary = path.join(baseDir, `${symbol}_${timeframe}.csv`);
        let filePath = primary;
        if (!fs.existsSync(filePath)) {
            const fallbackMap = {
                'D1': ['D'],
                'H12': ['12H'],
                'H4': ['4H'],
                'H1': ['1H'],
                'W1': ['W'],
                'MN1': ['M','1M']
            };
            const fallbacks = fallbackMap[timeframe] || [];
            for (const fb of fallbacks) {
                const candidate = path.join(baseDir, `${symbol}_${fb}.csv`);
                if (fs.existsSync(candidate)) { filePath = candidate; break; }
            }
            if (!fs.existsSync(filePath)) {
                return res.status(404).json({ error: `CSV not found: ${primary}` });
            }
        }

        const stream = fs.createReadStream(filePath);
        const rl = readline.createInterface({ input: stream, crlfDelay: Infinity });

        let headers = [];
        const out = [];

        for await (const line of rl) {
            if (!line || line.trim() === '') continue;
            if (headers.length === 0) {
                headers = line.split(',').map(h => h.trim());
                continue;
            }
            const cols = line.split(',');
            // Expect columns: time,Open,High,Low,Close,Volume (from downloader)
            const idx = (name) => headers.indexOf(name);
            const t = cols[idx('time')] || cols[idx('Time')] || cols[0];
            const o = parseFloat(cols[idx('Open')]);
            const h = parseFloat(cols[idx('High')]);
            const l = parseFloat(cols[idx('Low')]);
            const c = parseFloat(cols[idx('Close')]);
            const vIdx = idx('Volume') >= 0 ? idx('Volume') : idx('TickVolume');
            const v = vIdx >= 0 ? parseFloat(cols[vIdx]) : 0;

            // Standardize timestamp to ISO without trailing 'Z' (frontend appends 'Z')
            const iso = new Date(t).toISOString();
            const ts = iso.endsWith('Z') ? iso.slice(0, -1) : iso;
            out.push({ timestamp: ts, open: o, high: h, low: l, close: c, volume: v });
        }

        // Optional filtering by start_date/end_date and limit
        const { start_date, end_date, limit } = req.query || {};
        let filtered = out;
        const toUnix = (s) => {
            if (!s) return null;
            // timestamps in out are ISO without Z; frontend may send without Z too
            const d = new Date(s.endsWith('Z') ? s : `${s}Z`);
            const t = d.getTime();
            return isNaN(t) ? null : t;
        };
        if (start_date || end_date) {
            const startT = toUnix(start_date);
            const endT = toUnix(end_date);
            filtered = filtered.filter(row => {
                const t = toUnix(row.timestamp);
                if (t == null) return false;
                if (startT != null && t < startT) return false;
                if (endT != null && t >= endT) return false;
                return true;
            });
        }
        if (limit) {
            const n = parseInt(limit, 10);
            if (!isNaN(n) && n > 0 && filtered.length > n) {
                filtered = filtered.slice(filtered.length - n);
            }
        }

        return res.json(filtered);
    } catch (err) {
        console.error('getCsvCandles error:', err);
        return res.status(500).json({ error: 'Failed to read CSV candles' });
    }
};
