import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import List, Dict

import pytz
import pandas as pd
from decouple import config

# Optional local credentials module (not committed to git)
creds = None
try:
    from . import mt5_credentials as creds  # type: ignore
except Exception:
    try:
        # Absolute import if run without -m but from project root
        from algotrader.tools import mt5_credentials as creds  # type: ignore
    except Exception:
        try:
            # Plain import if CWD is tools directory
            import mt5_credentials as creds  # type: ignore
        except Exception:
            creds = None

try:
    import MetaTrader5 as mt5
except ImportError as e:
    print("MetaTrader5 package not installed. Please install it first: pip install MetaTrader5", file=sys.stderr)
    raise

# Timeframe mapping for CLI strings
TIMEFRAME_BY_NAME = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "H12": mt5.TIMEFRAME_H12,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

TIMEFRAME_NAMES = {v: k for k, v in TIMEFRAME_BY_NAME.items()}

def initialize_mt5() -> None:
    """Initialize MT5 connection using credentials file if present, else environment variables."""
    # Prefer local credentials module if available
    if creds is not None:
        terminal_path = getattr(creds, "MT5_PATH", r"C:\\Program Files\\MetaTrader 5\\terminal64.exe")
        login = getattr(creds, "MT5_LOGIN", None)
        password = getattr(creds, "MT5_PASSWORD", None)
        server = getattr(creds, "MT5_SERVER", None)
    else:
        terminal_path = config("MT5_PATH", default=r"C:\\Program Files\\MetaTrader 5\\terminal64.exe")
        login = config("MT5_LOGIN", cast=int, default=None)
        password = config("MT5_PASSWORD", default=None)
        server = config("MT5_SERVER", default=None)

    if not mt5.initialize(path=terminal_path):
        raise RuntimeError(f"MT5 initialize failed, error: {mt5.last_error()}")

    if login and password and server:
        if not mt5.login(login=login, password=password, server=server):
            raise RuntimeError(f"MT5 login failed, error: {mt5.last_error()}")


def get_candles_with_timeframe(symbol: str, timeframe: int, days_back: int = 100,
                                start_date: datetime | None = None,
                                end_date: datetime | None = None) -> pd.DataFrame | None:
    """Download candle data for a symbol with specified timeframe and date range."""
    timezone = pytz.timezone("Etc/UTC")

    if start_date is not None:
        utc_from = start_date.replace(tzinfo=timezone) if start_date.tzinfo is None else start_date
        utc_to = (end_date.replace(tzinfo=timezone) if end_date and end_date.tzinfo is None else end_date) or datetime.now(timezone)
    else:
        utc_to = datetime.now(timezone)
        utc_from = utc_to - timedelta(days=days_back)

    rates = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)
    if rates is None:
        print(f"Failed to get {TIMEFRAME_NAMES.get(timeframe, timeframe)} rates for {symbol}")
        return None

    df = pd.DataFrame(rates)
    if df.empty:
        print(f"No data returned for {symbol} {TIMEFRAME_NAMES.get(timeframe, timeframe)}")
        return None

    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)

    df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'tick_volume': 'Volume'
    }, inplace=True)

    # Ensure only expected columns are kept if present
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col not in df.columns:
            # Some brokers provide 'real_volume'; keep both if available
            if col == 'Volume' and 'real_volume' in df.columns:
                df['Volume'] = df['real_volume']
            else:
                df[col] = pd.NA

    return df[['Open', 'High', 'Low', 'Close', 'Volume']]


def download_multiple_pairs_multi_timeframe(pairs: List[str], timeframes: List[int],
                                            days_back: int = 100,
                                            start_date: datetime | None = None,
                                            end_date: datetime | None = None) -> Dict[str, Dict[int, pd.DataFrame]]:
    data: Dict[str, Dict[int, pd.DataFrame]] = {}
    for pair in pairs:
        data[pair] = {}
        print(f"\nDownloading {pair}...")
        for tf in timeframes:
            tf_name = TIMEFRAME_NAMES.get(tf, str(tf))
            print(f"  - {tf_name}...")
            df = get_candles_with_timeframe(pair, timeframe=tf, days_back=days_back,
                                             start_date=start_date, end_date=end_date)
            if df is not None:
                data[pair][tf] = df
                print(f"    Downloaded {len(df)} {tf_name} candles")
            else:
                print(f"    Failed to download {tf_name} data")
    return data


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download MT5 OHLCV data to CSVs")
    p.add_argument("--pairs", type=str, required=True, help="Comma-separated symbols, e.g. EURUSD,GBPUSD")
    p.add_argument("--timeframes", type=str, default="D1", help="Comma-separated timeframes, e.g. D1,H4,H1,M15")
    p.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD (optional)")
    p.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD (optional)")
    p.add_argument("--days_back", type=int, default=100, help="Days back (used if start not provided)")
    p.add_argument("--out", type=str, default="mt5_data/mt5_csv", help="Output directory for CSVs")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    pairs = [s.strip() for s in args.pairs.split(',') if s.strip()]
    tf_names = [s.strip().upper() for s in args.timeframes.split(',') if s.strip()]

    invalid = [t for t in tf_names if t not in TIMEFRAME_BY_NAME]
    if invalid:
        raise SystemExit(f"Invalid timeframe names: {invalid}. Valid: {list(TIMEFRAME_BY_NAME.keys())}")

    timeframes = [TIMEFRAME_BY_NAME[t] for t in tf_names]

    start = datetime.strptime(args.start, "%Y-%m-%d") if args.start else None
    end = datetime.strptime(args.end, "%Y-%m-%d") if args.end else None

    print("Initializing MT5...")
    initialize_mt5()
    try:
        all_data = download_multiple_pairs_multi_timeframe(
            pairs=pairs,
            timeframes=timeframes,
            days_back=args.days_back,
            start_date=start,
            end_date=end,
        )

        out_dir = args.out
        os.makedirs(out_dir, exist_ok=True)

        saved = []
        for pair, tf_map in all_data.items():
            for tf, df in tf_map.items():
                tf_name = TIMEFRAME_NAMES.get(tf, str(tf))
                filename = os.path.join(out_dir, f"{pair}_{tf_name}.csv")
                df.to_csv(filename)
                saved.append(filename)
                print(f"Saved {pair} {tf_name} data to {filename}")

        print("\nSummary:")
        print(f"Pairs: {pairs}")
        print(f"Timeframes: {tf_names}")
        print(f"Files saved: {len(saved)}")
        print(f"Output dir: {os.path.abspath(out_dir)}")

    finally:
        mt5.shutdown()
        print("\nMT5 shutdown completed")


if __name__ == "__main__":
    main()
