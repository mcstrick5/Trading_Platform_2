import pandas as pd
import numpy as np

def BollingerBands(df: pd.DataFrame, n=20, s=2):
    typical_p = ( df.mid_c + df.mid_h + df.mid_l ) / 3
    stddev = typical_p.rolling(window=n).std()
    df['BB_MA'] = typical_p.rolling(window=n).mean()
    df['BB_UP'] = df['BB_MA'] + stddev * s
    df['BB_LW'] = df['BB_MA'] - stddev * s
    return df

def ATR(df: pd.DataFrame, n=14):
    prev_c = df.mid_c.shift(1)
    tr1 = df.mid_h - df.mid_l
    tr2 = abs(df.mid_h - prev_c)
    tr3 = abs(prev_c - df.mid_l)
    tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
    df[f"ATR_{n}"] = tr.rolling(window=n).mean()
    return df

def KeltnerChannels(df: pd.DataFrame, n_ema=20, n_atr=10):
    df['EMA'] = df.mid_c.ewm(span=n_ema, min_periods=n_ema).mean()
    df = ATR(df, n=n_atr)
    c_atr = f"ATR_{n_atr}"
    df['KeUp'] = df[c_atr] * 2 + df.EMA
    df['KeLo'] = df.EMA - df[c_atr] * 2
    df.drop(c_atr, axis=1, inplace=True)
    return df


def RSI(df: pd.DataFrame, n=14):
    alpha = 1.0 / n
    gains = df.mid_c.diff()

    wins = pd.Series([ x if x >= 0 else 0.0 for x in gains ], name="wins")
    losses = pd.Series([ x * -1 if x < 0 else 0.0 for x in gains ], name="losses")

    wins_rma = wins.ewm(min_periods=n, alpha=alpha).mean()
    losses_rma = losses.ewm(min_periods=n, alpha=alpha).mean()

    rs = wins_rma / losses_rma

    df[f"RSI_{n}"] = 100.0 - (100.0 / (1.0 + rs))
    return df

def MACD(df: pd.DataFrame, n_slow=26, n_fast=12, n_signal=9):

    ema_long = df.mid_c.ewm(min_periods=n_slow, span=n_slow).mean()
    ema_short = df.mid_c.ewm(min_periods=n_fast, span=n_fast).mean()

    df['MACD'] = ema_short - ema_long
    df['SIGNAL'] = df.MACD.ewm(min_periods=n_signal, span=n_signal).mean()
    df['HIST'] = df.MACD - df.SIGNAL

    return df

def SMA(df: pd.DataFrame, column='mid_c', period=20):
    """Simple Moving Average"""
    df[f'SMA_{period}'] = df[column].rolling(window=period).mean()
    return df

def EMA(df: pd.DataFrame, column='mid_c', period=20):
    """Exponential Moving Average"""
    df[f'EMA_{period}'] = df[column].ewm(span=period, min_periods=period).mean()
    return df

def Stochastic(df: pd.DataFrame, k_period=14, d_period=3):
    """Stochastic Oscillator"""
    # %K = (Current Close - Lowest Low) / (Highest High - Lowest Low) * 100
    low_min = df.mid_l.rolling(window=k_period).min()
    high_max = df.mid_h.rolling(window=k_period).max()
    
    df['STOCH_K'] = 100 * ((df.mid_c - low_min) / (high_max - low_min))
    df['STOCH_D'] = df['STOCH_K'].rolling(window=d_period).mean()
    return df

def ADX(df: pd.DataFrame, period=14):
    """Average Directional Index"""
    # True Range
    df['TR'] = pd.DataFrame({
        'hl': df.mid_h - df.mid_l,
        'hc': abs(df.mid_h - df.mid_c.shift(1)),
        'lc': abs(df.mid_l - df.mid_c.shift(1))
    }).max(axis=1)
    
    # Plus and Minus Directional Movement
    df['DM+'] = np.where(
        (df.mid_h - df.mid_h.shift(1)) > (df.mid_l.shift(1) - df.mid_l),
        np.maximum(df.mid_h - df.mid_h.shift(1), 0),
        0
    )
    df['DM-'] = np.where(
        (df.mid_l.shift(1) - df.mid_l) > (df.mid_h - df.mid_h.shift(1)),
        np.maximum(df.mid_l.shift(1) - df.mid_l, 0),
        0
    )
    
    # Smoothed TR and DM
    df['ATR'] = df['TR'].rolling(window=period).mean()
    df['DM+_smooth'] = df['DM+'].rolling(window=period).mean()
    df['DM-_smooth'] = df['DM-'].rolling(window=period).mean()
    
    # Directional Indicators
    df['DI+'] = 100 * (df['DM+_smooth'] / df['ATR'])
    df['DI-'] = 100 * (df['DM-_smooth'] / df['ATR'])
    
    # Directional Index
    df['DX'] = 100 * abs(df['DI+'] - df['DI-']) / (df['DI+'] + df['DI-'])
    
    # Average Directional Index
    df['ADX'] = df['DX'].rolling(window=period).mean()
    
    # Clean up intermediate columns
    df.drop(['TR', 'DM+', 'DM-', 'ATR', 'DM+_smooth', 'DM-_smooth', 'DX'], axis=1, inplace=True)
    
    return df

def OBV(df: pd.DataFrame):
    """On-Balance Volume"""
    df['OBV'] = (np.sign(df.mid_c.diff()) * df['volume']).fillna(0).cumsum()
    return df

def VWAP(df: pd.DataFrame):
    """Volume Weighted Average Price"""
    # Assuming df has a datetime index
    df['date'] = df.index.date
    
    typical_price = (df.mid_h + df.mid_l + df.mid_c) / 3
    df['TP_Vol'] = typical_price * df['volume']
    
    df['cumulative_TP_Vol'] = df.groupby('date')['TP_Vol'].cumsum()
    df['cumulative_volume'] = df.groupby('date')['volume'].cumsum()
    
    df['VWAP'] = df['cumulative_TP_Vol'] / df['cumulative_volume']
    
    # Clean up
    df.drop(['date', 'TP_Vol', 'cumulative_TP_Vol', 'cumulative_volume'], axis=1, inplace=True)
    return df

def Ichimoku(df: pd.DataFrame, tenkan=9, kijun=26, senkou_b=52):
    """Ichimoku Cloud"""
    # Tenkan-sen (Conversion Line)
    tenkan_high = df.mid_h.rolling(window=tenkan).max()
    tenkan_low = df.mid_l.rolling(window=tenkan).min()
    df['TENKAN'] = (tenkan_high + tenkan_low) / 2
    
    # Kijun-sen (Base Line)
    kijun_high = df.mid_h.rolling(window=kijun).max()
    kijun_low = df.mid_l.rolling(window=kijun).min()
    df['KIJUN'] = (kijun_high + kijun_low) / 2
    
    # Senkou Span A (Leading Span A)
    df['SENKOU_A'] = ((df['TENKAN'] + df['KIJUN']) / 2).shift(kijun)
    
    # Senkou Span B (Leading Span B)
    senkou_b_high = df.mid_h.rolling(window=senkou_b).max()
    senkou_b_low = df.mid_l.rolling(window=senkou_b).min()
    df['SENKOU_B'] = ((senkou_b_high + senkou_b_low) / 2).shift(kijun)
    
    # Chikou Span (Lagging Span)
    df['CHIKOU'] = df.mid_c.shift(-kijun)
    
    return df

def PSAR(df: pd.DataFrame, iaf=0.02, maxaf=0.2):
    """Parabolic SAR"""
    length = len(df)
    df['PSAR'] = df.mid_c.copy()
    df['PSARHIGH'] = 0.0
    df['PSARLOW'] = 0.0
    df['PSARDIR'] = 0.0
    df['PSARAF'] = 0.0
    
    # Initialize
    df.loc[0, 'PSARHIGH'] = df.loc[0, 'mid_h']
    df.loc[0, 'PSARLOW'] = df.loc[0, 'mid_l']
    df.loc[0, 'PSARDIR'] = 1  # Start as uptrend
    df.loc[0, 'PSARAF'] = iaf
    df.loc[0, 'PSAR'] = df.loc[0, 'PSARLOW']
    
    # Calculate PSAR
    for i in range(1, length):
        psar = df.loc[i-1, 'PSAR']
        direction = df.loc[i-1, 'PSARDIR']
        af = df.loc[i-1, 'PSARAF']
        high_point = df.loc[i-1, 'PSARHIGH']
        low_point = df.loc[i-1, 'PSARLOW']
        
        # Uptrend
        if direction == 1:
            # Update PSAR
            psar = psar + af * (high_point - psar)
            # Ensure PSAR is less than current or prior two lows
            psar = min(psar, df.loc[max(0, i-2), 'mid_l'], df.loc[max(0, i-1), 'mid_l'])
            
            # Update direction if price penetrates PSAR
            if df.loc[i, 'mid_l'] < psar:
                direction = -1
                psar = high_point
                high_point = df.loc[i, 'mid_h']
                low_point = df.loc[i, 'mid_l']
                af = iaf
            else:
                # Update EP and AF if new high
                if df.loc[i, 'mid_h'] > high_point:
                    high_point = df.loc[i, 'mid_h']
                    af = min(af + iaf, maxaf)
        # Downtrend
        else:
            # Update PSAR
            psar = psar - af * (psar - low_point)
            # Ensure PSAR is greater than current or prior two highs
            psar = max(psar, df.loc[max(0, i-2), 'mid_h'], df.loc[max(0, i-1), 'mid_h'])
            
            # Update direction if price penetrates PSAR
            if df.loc[i, 'mid_h'] > psar:
                direction = 1
                psar = low_point
                high_point = df.loc[i, 'mid_h']
                low_point = df.loc[i, 'mid_l']
                af = iaf
            else:
                # Update EP and AF if new low
                if df.loc[i, 'mid_l'] < low_point:
                    low_point = df.loc[i, 'mid_l']
                    af = min(af + iaf, maxaf)
        
        df.loc[i, 'PSAR'] = psar
        df.loc[i, 'PSARDIR'] = direction
        df.loc[i, 'PSARHIGH'] = high_point
        df.loc[i, 'PSARLOW'] = low_point
        df.loc[i, 'PSARAF'] = af
    
    # Clean up intermediate columns
    df.drop(['PSARHIGH', 'PSARLOW', 'PSARDIR', 'PSARAF'], axis=1, inplace=True)
    
    return df

def CCI(df: pd.DataFrame, period=20):
    """Commodity Channel Index"""
    typical_price = (df.mid_h + df.mid_l + df.mid_c) / 3
    moving_avg = typical_price.rolling(window=period).mean()
    mean_deviation = abs(typical_price - moving_avg).rolling(window=period).mean()
    
    df['CCI'] = (typical_price - moving_avg) / (0.015 * mean_deviation)
    return df

def WilliamsR(df: pd.DataFrame, period=14):
    """Williams %R"""
    highest_high = df.mid_h.rolling(window=period).max()
    lowest_low = df.mid_l.rolling(window=period).min()
    
    df['WILLIAMS_R'] = -100 * (highest_high - df.mid_c) / (highest_high - lowest_low)
    return df

def CMF(df: pd.DataFrame, period=20):
    """Chaikin Money Flow"""
    mfv = ((df.mid_c - df.mid_l) - (df.mid_h - df.mid_c)) / (df.mid_h - df.mid_l) * df['volume']
    df['CMF'] = mfv.rolling(window=period).sum() / df['volume'].rolling(window=period).sum()
    return df

def DonchianChannels(df: pd.DataFrame, period=20):
    """Donchian Channels"""
    df['DC_UPPER'] = df.mid_h.rolling(window=period).max()
    df['DC_LOWER'] = df.mid_l.rolling(window=period).min()
    df['DC_MIDDLE'] = (df['DC_UPPER'] + df['DC_LOWER']) / 2
    return df

def SuperTrend(df: pd.DataFrame, atr_period=10, multiplier=3.0):
    """SuperTrend Indicator"""
    # Calculate ATR
    df = ATR(df, n=atr_period)
    atr_col = f"ATR_{atr_period}"
    
    # Basic Upper and Lower Bands
    df['basic_upper'] = ((df.mid_h + df.mid_l) / 2) + (multiplier * df[atr_col])
    df['basic_lower'] = ((df.mid_h + df.mid_l) / 2) - (multiplier * df[atr_col])
    
    # SuperTrend
    df['SUPERTREND'] = 0.0
    df['ST_DIRECTION'] = 0  # 1 for uptrend, -1 for downtrend
    
    # Set initial values
    for i in range(1, len(df)):
        if df.loc[i, 'mid_c'] > df.loc[i-1, 'basic_upper']:
            df.loc[i, 'ST_DIRECTION'] = 1
        elif df.loc[i, 'mid_c'] < df.loc[i-1, 'basic_lower']:
            df.loc[i, 'ST_DIRECTION'] = -1
        else:
            df.loc[i, 'ST_DIRECTION'] = df.loc[i-1, 'ST_DIRECTION']
            
            if df.loc[i, 'ST_DIRECTION'] == 1 and df.loc[i, 'basic_lower'] < df.loc[i-1, 'basic_lower']:
                df.loc[i, 'basic_lower'] = df.loc[i-1, 'basic_lower']
            
            if df.loc[i, 'ST_DIRECTION'] == -1 and df.loc[i, 'basic_upper'] > df.loc[i-1, 'basic_upper']:
                df.loc[i, 'basic_upper'] = df.loc[i-1, 'basic_upper']
                
        # Determine SuperTrend value
        if df.loc[i, 'ST_DIRECTION'] == 1:
            df.loc[i, 'SUPERTREND'] = df.loc[i, 'basic_lower']
        else:
            df.loc[i, 'SUPERTREND'] = df.loc[i, 'basic_upper']
    
    # Clean up
    df.drop(['basic_upper', 'basic_lower'], axis=1, inplace=True)
    
    return df

def Aroon(df: pd.DataFrame, period=25):
    """Aroon Indicator"""
    # Aroon Up: ((period - periods since highest high) / period) * 100
    rolling_high = df.mid_h.rolling(window=period).max()
    df['days_since_high'] = df.mid_h.rolling(window=period).apply(lambda x: period - x.argmax() - 1)
    df['AROON_UP'] = 100 * (period - df['days_since_high']) / period
    
    # Aroon Down: ((period - periods since lowest low) / period) * 100
    rolling_low = df.mid_l.rolling(window=period).min()
    df['days_since_low'] = df.mid_l.rolling(window=period).apply(lambda x: period - x.argmin() - 1)
    df['AROON_DOWN'] = 100 * (period - df['days_since_low']) / period
    
    # Aroon Oscillator: Aroon Up - Aroon Down
    df['AROON_OSC'] = df['AROON_UP'] - df['AROON_DOWN']
    
    # Clean up
    df.drop(['days_since_high', 'days_since_low'], axis=1, inplace=True)
    
    return df

def ZigZag(df: pd.DataFrame, deviation=5.0):
    """ZigZag Indicator"""
    df['ZIGZAG'] = 0.0
    df['ZIGZAG_PIVOT'] = False
    
    # Find swing points
    last_price = df.iloc[0].mid_c
    last_position = 0
    trend_direction = 0  # 0 for undefined, 1 for up, -1 for down
    
    for i in range(1, len(df)):
        current_price = df.iloc[i].mid_c
        price_change = (current_price - last_price) / last_price * 100
        
        if abs(price_change) >= deviation:
            df.loc[df.index[last_position], 'ZIGZAG'] = last_price
            df.loc[df.index[last_position], 'ZIGZAG_PIVOT'] = True
            last_price = current_price
            last_position = i
            trend_direction = 1 if price_change > 0 else -1
    
    # Make sure the last point is marked
    df.loc[df.index[last_position], 'ZIGZAG'] = last_price
    df.loc[df.index[last_position], 'ZIGZAG_PIVOT'] = True
    
    return df

def ROC(df: pd.DataFrame, period=12):
    """Rate of Change"""
    df[f'ROC_{period}'] = ((df.mid_c - df.mid_c.shift(period)) / df.mid_c.shift(period)) * 100
    return df

def MFI(df: pd.DataFrame, period=14):
    """Money Flow Index"""
    typical_price = (df.mid_h + df.mid_l + df.mid_c) / 3
    money_flow = typical_price * df['volume']
    
    # Get positive and negative money flow
    positive_flow = pd.Series(0.0, index=df.index)
    negative_flow = pd.Series(0.0, index=df.index)
    
    # Calculate price changes
    price_change = typical_price.diff()
    
    # Set positive/negative money flow based on price change
    positive_flow[price_change > 0] = money_flow[price_change > 0]
    negative_flow[price_change < 0] = money_flow[price_change < 0]
    
    # Get money flow ratio
    positive_mf_sum = positive_flow.rolling(window=period).sum()
    negative_mf_sum = negative_flow.rolling(window=period).sum()
    
    money_flow_ratio = positive_mf_sum / negative_mf_sum
    
    # Calculate MFI
    df['MFI'] = 100 - (100 / (1 + money_flow_ratio))
    
    return df

























