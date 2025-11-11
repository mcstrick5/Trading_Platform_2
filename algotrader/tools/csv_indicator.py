import argparse
import json
import os
import sys
from datetime import datetime

import pandas as pd

# Import user indicators (works when run as a script)
try:
    # If executed as a package module
    from . import user_indicators as ui  # type: ignore
except Exception:
    # Fallback to indicators in backtester/src/indicators
    THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
    INDICATORS_DIR = os.path.join(PROJECT_ROOT, 'algotrader', 'backtester', 'src', 'indicators')
    # Also allow local tools (in case a copy exists here later)
    for p in [THIS_DIR, INDICATORS_DIR]:
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import user_indicators as ui  # type: ignore
    except Exception as e:
        raise ImportError(f"Failed to import user_indicators from {INDICATORS_DIR}") from e


TF_ALIAS = {
    'D': 'D1', '1D': 'D1', 'DAILY': 'D1',
    '12H': 'H12', 'H12': 'H12',
    '4H': 'H4', 'H4': 'H4',
    '1H': 'H1', 'H1': 'H1',
    'W': 'W1', '1W': 'W1', 'WEEKLY': 'W1',
    'M': 'MN1', '1M': 'MN1', 'MONTHLY': 'MN1',
    '30M': 'M30', 'M30': 'M30',
    '15M': 'M15', 'M15': 'M15',
    '5M': 'M5', 'M5': 'M5',
    '1M': 'M1', 'M1': 'M1', '1MIN': 'M1',
}

TF_MINUTES = {
    1: 'M1', 5: 'M5', 15: 'M15', 30: 'M30',
    60: 'H1', 240: 'H4', 720: 'H12', 1440: 'D1',
    10080: 'W1', 43200: 'MN1'
}


def normalize_timeframe(tf: str) -> str:
    s = str(tf).upper()
    if s in TF_ALIAS:
        return TF_ALIAS[s]
    try:
        m = int(s)
        if m in TF_MINUTES:
            return TF_MINUTES[m]
    except Exception:
        pass
    # Already normalized?
    return s


def load_csv(data_dir: str, symbol: str, timeframe: str) -> pd.DataFrame:
    """Load CSV by symbol/timeframe and return DataFrame indexed by time."""
    tf = normalize_timeframe(timeframe)
    primary = os.path.join(data_dir, f"{symbol}_{tf}.csv")
    fallback_map = {
        'D1': ['D'], 'H12': ['12H'], 'H4': ['4H'], 'H1': ['1H'], 'W1': ['W'], 'MN1': ['M', '1M']
    }
    path = primary
    if not os.path.exists(path):
        for fb in fallback_map.get(tf, []):
            candidate = os.path.join(data_dir, f"{symbol}_{fb}.csv")
            if os.path.exists(candidate):
                path = candidate
                break
    if not os.path.exists(path):
        raise FileNotFoundError(primary)

    df = pd.read_csv(path)
    # Expect 'time' column; parse
    time_col = 'time' if 'time' in df.columns else df.columns[0]
    df[time_col] = pd.to_datetime(df[time_col])
    df.set_index(time_col, inplace=True)
    df.sort_index(inplace=True)

    # Standard expected columns from downloader: Open, High, Low, Close, Volume
    # Map to mid_* for user's indicators
    rename_map = {}
    for col in df.columns:
        lc = col.lower()
        if lc == 'open':
            rename_map[col] = 'Open'
        elif lc == 'high':
            rename_map[col] = 'High'
        elif lc == 'low':
            rename_map[col] = 'Low'
        elif lc == 'close':
            rename_map[col] = 'Close'
        elif lc == 'volume':
            rename_map[col] = 'Volume'
    if rename_map:
        df.rename(columns=rename_map, inplace=True)

    # Coerce OHLCV to numeric
    for col in ['Open','High','Low','Close','Volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Create mid_* aliases
    if 'Close' in df.columns:
        df['mid_c'] = df['Close']
    if 'Open' in df.columns:
        df['mid_o'] = df['Open']
    if 'High' in df.columns:
        df['mid_h'] = df['High']
    if 'Low' in df.columns:
        df['mid_l'] = df['Low']
    if 'Volume' in df.columns:
        df['volume'] = df['Volume']

    return df


def to_iso_no_z(dt: pd.Timestamp) -> str:
    s = pd.to_datetime(dt).to_pydatetime().isoformat(timespec='milliseconds')
    # Remove trailing Z if any (should be naive or timezone-aware)
    return s[:-1] if s.endswith('Z') else s


def compute_indicator(df: pd.DataFrame, name: str, params: dict) -> list[dict]:
    name_u = name.strip().upper()
    out_rows: list[dict] = []

    if name_u == 'SMA':
        window = int(params.get('window', 20))
        src = params.get('source', 'mid_c')
        df2 = ui.SMA(df.copy(), column=src, period=window)
        key = f'SMA_{window}'
        for ts, val in df2[key].dropna().items():
            out_rows.append({ 'timestamp': to_iso_no_z(ts), 'sma': float(val) })
        return out_rows

    if name_u == 'RSI':
        length = int(params.get('length', 14))
        # Try user's implementation first
        try:
            df2 = ui.RSI(df.copy(), n=length)
        except Exception:
            df2 = pd.DataFrame(index=df.index)
        key = f'RSI_{length}'
        series = None
        if key in df2.columns:
            series = df2[key]
        else:
            # fallback: first RSI_* column
            rsi_cols = [c for c in df2.columns if str(c).upper().startswith('RSI_')]
            if rsi_cols:
                series = df2[rsi_cols[0]]
        # If series missing or all NaN, compute robust RSI here with aligned index
        if series is None or series.dropna().empty:
            delta = df['mid_c'].diff()
            gains = delta.clip(lower=0)
            losses = (-delta).clip(lower=0)
            alpha = 1.0 / length
            avg_gain = gains.ewm(alpha=alpha, min_periods=length, adjust=False).mean()
            avg_loss = losses.ewm(alpha=alpha, min_periods=length, adjust=False).mean()
            rs = avg_gain / avg_loss
            series = 100.0 - (100.0 / (1.0 + rs))
        for ts, val in series.dropna().items():
            out_rows.append({ 'timestamp': to_iso_no_z(ts), 'rsi': float(val) })
        return out_rows

    if name_u in ('BBANDS', 'BOLLINGER', 'BOLLINGERBANDS'):
        n = int(params.get('length', 20))
        s = float(params.get('std', 2))
        df2 = ui.BollingerBands(df.copy(), n=n, s=s)
        for ts, row in df2[['BB_LW','BB_MA','BB_UP']].dropna().iterrows():
            out_rows.append({
                'timestamp': to_iso_no_z(ts),
                'lower': float(row['BB_LW']),
                'mid': float(row['BB_MA']),
                'upper': float(row['BB_UP'])
            })
        return out_rows

    if name_u == 'MACD':
        n_slow = int(params.get('slow', 26))
        n_fast = int(params.get('fast', 12))
        n_signal = int(params.get('signal', 9))
        df2 = ui.MACD(df.copy(), n_slow=n_slow, n_fast=n_fast, n_signal=n_signal)
        for ts, row in df2[['MACD','SIGNAL','HIST']].dropna().iterrows():
            out_rows.append({
                'timestamp': to_iso_no_z(ts),
                'macd': float(row['MACD']),
                'signal': float(row['SIGNAL']),
                'histogram': float(row['HIST'])
            })
        return out_rows

    # Volume histogram (uses Volume or volume column)
    if name_u == 'VOL':
        vol_series = None
        if 'volume' in df.columns:
            vol_series = df['volume']
        elif 'Volume' in df.columns:
            vol_series = df['Volume']
        else:
            # If no volume column, synthesize zeros
            vol_series = pd.Series(0, index=df.index)
        for ts, val in vol_series.dropna().items():
            out_rows.append({ 'timestamp': to_iso_no_z(ts), 'volume': float(val) })
        return out_rows

    # Relative Volume: vol / SMA(vol, length)
    if name_u in ('RVOL', 'RELATIVEVOLUME', 'RELATIVE_VOLUME'):
        length = int(params.get('length', 20))
        vol_series = None
        if 'volume' in df.columns:
            vol_series = df['volume']
        elif 'Volume' in df.columns:
            vol_series = df['Volume']
        else:
            vol_series = pd.Series(0, index=df.index)
        sma = vol_series.rolling(length, min_periods=length).mean()
        rvol = vol_series / sma
        for ts, val in rvol.dropna().items():
            out_rows.append({ 'timestamp': to_iso_no_z(ts), 'rvol': float(val) })
        return out_rows

    raise ValueError(f"Unsupported indicator name: {name}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--timeframe', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--data_dir', default=None)
    p.add_argument('--params', default=None, help='JSON string or key=value pairs separated by commas')
    args = p.parse_args()

    data_dir = args.data_dir or os.environ.get('MT5_DATA_DIR')
    if not data_dir:
        raise SystemExit('MT5_DATA_DIR not set and --data_dir not provided')

    # parse params
    params: dict = {}
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError:
            # key=value,key=value
            for part in args.params.split(','):
                if '=' in part:
                    k, v = part.split('=', 1)
                    k = k.strip()
                    v = v.strip()
                    if v.isdigit():
                        v = int(v)
                    else:
                        try:
                            v = float(v)
                        except Exception:
                            pass
                    params[k] = v

    df = load_csv(data_dir, args.symbol, args.timeframe)
    rows = compute_indicator(df, args.name, params)
    print(json.dumps(rows))


if __name__ == '__main__':
    main()
