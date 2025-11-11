import os
import sys
import json
from datetime import datetime, timedelta, timezone
import pandas as pd
import pytz

# Make sure project root is on sys.path so absolute import works when run as a script
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    # Prefer absolute import to be consistent with backend spawns
    from algotrader.tools.mt5_downloader import TIMEFRAME_BY_NAME, TIMEFRAME_NAMES, get_candles_with_timeframe  # type: ignore
except Exception:
    # Fallback to relative if package context exists
    from .mt5_downloader import TIMEFRAME_BY_NAME, TIMEFRAME_NAMES, get_candles_with_timeframe  # type: ignore

import MetaTrader5 as mt5

def parse_symbol_tf(filename: str):
    # expects SYMBOL_TF.csv
    base = os.path.splitext(os.path.basename(filename))[0]
    if '_' not in base:
        return None, None
    sym, tf_name = base.rsplit('_', 1)
    return sym, tf_name.upper()

_DURATIONS = {
    'M1': timedelta(minutes=1), 'M5': timedelta(minutes=5), 'M15': timedelta(minutes=15), 'M30': timedelta(minutes=30),
    'H1': timedelta(hours=1), 'H4': timedelta(hours=4), 'H12': timedelta(hours=12),
    'D1': timedelta(days=1), 'W1': timedelta(weeks=1)
}

def read_last_timestamp(csv_path: str) -> datetime | None:
    try:
        # Read last 500 lines (fast path) then take last non-empty row
        df = pd.read_csv(csv_path)
        if df.empty:
            return None
        col = 'time' if 'time' in df.columns else df.columns[0]
        ts = pd.to_datetime(df[col]).iloc[-1]
        if ts.tzinfo is None:
            return ts.tz_localize('UTC')
        return ts.tz_convert('UTC')
    except Exception:
        return None


def append_unique(csv_path: str, new_df: pd.DataFrame) -> int:
    if new_df is None or new_df.empty:
        return 0
    try:
        old = pd.read_csv(csv_path)
    except Exception:
        old = pd.DataFrame()
    df = old
    if not new_df.empty:
        # Ensure same columns naming
        nd = new_df.copy()
        if 'time' not in nd.columns:
            # mt5_downloader returns index=DatetimeIndex
            nd = nd.reset_index()
        # Standardize column names
        rename = { 'open':'Open','high':'High','low':'Low','close':'Close','tick_volume':'Volume','real_volume':'Volume','spread':'Spread' }
        nd = nd.rename(columns=rename)
        if 'Volume' not in nd.columns and 'tick_volume' in nd.columns:
            nd['Volume'] = nd['tick_volume']
        # Merge
        if df.empty:
            df = nd
        else:
            df = pd.concat([df, nd], ignore_index=True)
        # Drop dups by time
        time_col = 'time' if 'time' in df.columns else df.columns[0]
        df[time_col] = pd.to_datetime(df[time_col])
        df = df.drop_duplicates(subset=[time_col]).sort_values(by=time_col)
    # Write atomically
    tmp = csv_path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, csv_path)
    return len(new_df)


def run_update(data_dir: str) -> dict:
    tz = pytz.timezone('Etc/UTC')
    summary = { 'updated': [], 'skipped': [], 'errors': [] }

    if not mt5.initialize():
        summary['errors'].append('Failed to initialize MT5')
        return summary
    try:
        files = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.lower().endswith('.csv')]
        for f in sorted(files):
            sym, tf_name = parse_symbol_tf(f)
            if not sym or tf_name not in TIMEFRAME_BY_NAME:
                continue
            last_ts = read_last_timestamp(f)
            dur = _DURATIONS.get(tf_name, timedelta(days=1))
            if last_ts is None:
                # Nothing to append; skip (full file will be created by downloader when needed)
                summary['skipped'].append({ 'symbol': sym, 'timeframe': tf_name, 'reason': 'empty-csv' })
                continue
            utc_from = (last_ts + dur).astimezone(tz)
            utc_to = datetime.now(tz)
            if utc_from >= utc_to:
                summary['skipped'].append({ 'symbol': sym, 'timeframe': tf_name, 'reason': 'up-to-date' })
                continue
            tf_val = TIMEFRAME_BY_NAME[tf_name]
            try:
                df_new = get_candles_with_timeframe(sym, timeframe=tf_val, start_date=utc_from, end_date=utc_to)
                n = append_unique(f, df_new if df_new is not None else pd.DataFrame())
                if n > 0:
                    summary['updated'].append({ 'symbol': sym, 'timeframe': tf_name, 'rows': n })
                else:
                    summary['skipped'].append({ 'symbol': sym, 'timeframe': tf_name, 'reason': 'no-new-rows' })
            except Exception as e:
                summary['errors'].append({ 'symbol': sym, 'timeframe': tf_name, 'error': str(e) })
        return summary
    finally:
        mt5.shutdown()


if __name__ == '__main__':
    data_dir = os.environ.get('MT5_DATA_DIR') or os.path.join('mt5_data', 'mt5_csv')
    result = run_update(data_dir)
    print(json.dumps(result))
