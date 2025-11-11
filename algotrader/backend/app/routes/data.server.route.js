const data = require('../controllers/data.server.controller.js');

module.exports = function(app) {
    app.get('/api/candles/:symbolID/:timeframe', data.getCandles);
    app.get('/api/markets', data.getMarkets);
    app.put('/api/markets', data.insertMarket);
    app.get('/api/csv-candles/:symbol/:timeframe', data.getCsvCandles);
    app.get('/api/csv-indicator/:symbol', data.getCsvIndicator);
    app.post('/api/csv-refresh', data.csvRefresh);
    // CSV-backed versions for frontend's data-accessor proxy
    app.get('/api/data-accessor/markets', data.getCsvMarkets);
    app.get('/api/data-accessor/candles/:symbol', data.getCsvCandlesByQuery);
};