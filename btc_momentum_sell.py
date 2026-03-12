#!/usr/bin/env python3
"""
BTC Momentum Scoring System v3.0 — SELL Side
JP Trust Learning

Mirror of the Buy score: gives HIGH scores when bearish conditions are strong.
Adapted from Gold Momentum Sell v3.0 for BTC characteristics.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
import os, sys

ROLLING_WINDOW = 252
LOOKBACK = {'1W': 5, '1M': 21, '3M': 63, '6M': 126, '1Y': 252}
WEIGHTS = {'1Y': 0.30, '6M': 0.25, '3M': 0.20, '1M': 0.15, '1W': 0.10}
WEIGHT_ORDER = ['1Y', '6M', '3M', '1M', '1W']

RUN_TS = datetime.now(timezone.utc)
AS_OF = RUN_TS.strftime("%d/%m/%Y %H:%M UTC")
TS_FILE = RUN_TS.strftime("%d%m%Y_%H%M")

base_dir = os.path.dirname(os.path.abspath(__file__))

def load_price_csv(filename):
    path = os.path.join(base_dir, filename)
    if not os.path.exists(path):
        print(f"⚠️ {filename} not found — skipping")
        return None
    df = pd.read_csv(path, encoding='utf-8-sig')
    df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    return df

df = load_price_csv('btc_prices.csv')
df_dxy = load_price_csv('dxy_prices.csv')
df_vix = load_price_csv('vix_prices.csv')

if df is None:
    print("❌ btc_prices.csv not found — cannot continue")
    sys.exit(1)

BD2_idx = len(df) - 1
BD1_idx = len(df) - 6
BD1_date = df.iloc[BD1_idx]['Date']
BD2_date = df.iloc[BD2_idx]['Date']

print(f"BTC Momentum Scoring v3.0 — SELL Side")
print(f"{'='*55}")
print(f"Base Date 1: {BD1_date.strftime('%Y-%m-%d')} (idx={BD1_idx})")
print(f"Base Date 2: {BD2_date.strftime('%Y-%m-%d')} (idx={BD2_idx})")
print(f"Total BTC rows: {len(df)}")

# ── Shared calculation functions ──

def compute_return(closes, end_idx, period_days):
    start_idx = end_idx - period_days
    if start_idx < 0: return None
    return (closes[end_idx] - closes[start_idx]) / closes[start_idx] * 100

def rolling_percentile(series_values, current_val, window=ROLLING_WINDOW):
    valid = series_values[~np.isnan(series_values)]
    if len(valid) < 10: return 50.0
    count_below = np.sum(valid < current_val)
    return count_below / (len(valid) - 1) * 100 if len(valid) > 1 else 50.0

def calc_return_percentiles(df, base_idx):
    closes = df['Close'].values
    results = {}
    for period, days in LOOKBACK.items():
        current_ret = compute_return(closes, base_idx, days)
        if current_ret is None:
            results[period] = {'return': 0, 'percentile': 50}
            continue
        rolling_rets = []
        start = max(0, base_idx - ROLLING_WINDOW)
        for i in range(start, base_idx):
            r = compute_return(closes, i, days)
            if r is not None: rolling_rets.append(r)
        pctl = rolling_percentile(np.array(rolling_rets), current_ret) if rolling_rets else 50
        results[period] = {'return': current_ret, 'percentile': pctl}
    return results

def calc_volume_percentiles(df, base_idx):
    volumes = df['Volume'].values
    results = {}
    for period, days in LOOKBACK.items():
        end = base_idx + 1
        start = end - days
        if start < 0:
            results[period] = {'volume': 0, 'percentile': 50}
            continue
        current_vol = np.sum(volumes[start:end])
        rolling_vols = []
        roll_start = max(0, base_idx - ROLLING_WINDOW)
        for i in range(roll_start, base_idx):
            s = i + 1 - days
            if s < 0: continue
            rolling_vols.append(np.sum(volumes[s:i+1]))
        pctl = rolling_percentile(np.array(rolling_vols), current_vol) if rolling_vols else 50
        results[period] = {'volume': current_vol, 'percentile': pctl}
    return results

def weighted_percentile(pctl_dict):
    return sum(pctl_dict[p]['percentile'] * WEIGHTS[p] for p in WEIGHT_ORDER)

def calc_rsi(df, base_idx, period=14):
    start = base_idx - 29
    if start < 0: start = 0
    closes = df['Close'].values[start:base_idx+1]
    if len(closes) < 2: return 50
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    last_n = min(period, len(gains))
    avg_gain = np.mean(gains[-last_n:])
    avg_loss = np.mean(losses[-last_n:])
    if avg_loss == 0: return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))

def calc_ma(df, base_idx, window):
    start = base_idx + 1 - window
    if start < 0: return None
    return np.mean(df['Close'].values[start:base_idx+1])

def calc_volatility(df, base_idx):
    start = base_idx - 20
    if start < 0: start = 0
    closes = df['Close'].values[start:base_idx+1]
    if len(closes) < 2: return 0
    rets = np.diff(closes) / closes[:-1]
    return np.std(rets) * np.sqrt(365) * 100

def find_closest_idx(ext_df, target_date, max_gap_days=5):
    if ext_df is None: return None
    diffs = (ext_df['Date'] - target_date).abs()
    if diffs.min().days > max_gap_days: return None
    return diffs.idxmin()

def calc_external_return(ext_df, end_idx, period_days):
    if ext_df is None or end_idx is None: return None
    start_idx = end_idx - period_days
    if start_idx < 0: return None
    return (ext_df['Close'].values[end_idx] - ext_df['Close'].values[start_idx]) / ext_df['Close'].values[start_idx] * 100


# ══════════════════════════════════════════════════════
# SELL-SIDE SCORING FUNCTIONS (0-100 each)
# ══════════════════════════════════════════════════════

def d1_sell_score(wp_return):
    """D1s: FLIP return percentile — low returns = strong sell."""
    return 100 - wp_return

def d2_sell_score(wp_volume, ret_1m):
    """D2s: High volume + negative returns = selling pressure."""
    if wp_volume >= 70 and ret_1m < 0:
        return 80 + (wp_volume - 70) / 30 * 20
    elif wp_volume >= 70 and ret_1m >= 0:
        return 30 - (wp_volume - 70) / 30 * 10
    elif wp_volume < 70 and ret_1m < 0:
        return 40 + (70 - wp_volume) / 70 * 30
    else:
        return 10

def d3_sell_score(rsi):
    """D3s: Low RSI = strong bearish momentum."""
    if rsi < 30:   return 100
    if rsi < 40:   return 85
    if rsi < 50:   return 65
    if rsi > 80:   return 65
    if rsi > 70:   return 50
    if rsi >= 60:  return 20
    return 40

def d4_sell_score(price, ma50, ma200):
    """D4s: Price below MAs + Death Cross = bearish."""
    pts = 0
    if ma50 is not None and price < ma50: pts += 35
    if ma200 is not None and price < ma200: pts += 35
    if ma50 is not None and ma200 is not None and ma50 < ma200: pts += 30
    return min(pts, 100)

def d5_sell_score(vol):
    """D5s: HIGH vol = panic = strong sell. Thresholds for crypto."""
    if vol > 120: return 100
    if vol > 90:  return 90
    if vol > 75:  return 75
    if vol > 60:  return 60
    if vol > 45:  return 40
    if vol > 30:  return 20
    return 5

def calc_d6_sell_external(df_btc, btc_idx, df_dxy, df_vix):
    """
    D6s External — SELL Side (BTC = risk-on, so bearish when):
    - DXY strong + BTC down = risk-off confirmed
    - VIX high + BTC down = panic selling risk assets
    """
    btc_date = df_btc.iloc[btc_idx]['Date']
    btc_closes = df_btc['Close'].values
    btc_1m = compute_return(btc_closes, btc_idx, 21)
    if btc_1m is None: btc_1m = 0
    btc_down = btc_1m < 0

    dxy_score = 0
    dxy_1m = None
    dxy_signal = "N/A"
    
    if df_dxy is not None:
        dxy_idx = find_closest_idx(df_dxy, btc_date)
        if dxy_idx is not None:
            dxy_1m = calc_external_return(df_dxy, dxy_idx, 21)
            if dxy_1m is not None:
                dxy_up = dxy_1m > 0
                if btc_down and dxy_up:
                    dxy_score = +5
                    dxy_signal = "🔴 Risk-Off Confirmed (BTC down + strong $)"
                elif btc_down and not dxy_up:
                    dxy_score = +2
                    dxy_signal = "🟠 BTC Weakness (down despite weak $)"
                elif not btc_down and dxy_up:
                    dxy_score = 0
                    dxy_signal = "⚪ Mixed (BTC up + strong $)"
                else:
                    dxy_score = -5
                    dxy_signal = "🟢 Risk-On (BTC up + weak $)"

    vix_score = 0
    vix_level = None
    vix_signal = "N/A"
    
    if df_vix is not None:
        vix_idx = find_closest_idx(df_vix, btc_date)
        if vix_idx is not None:
            vix_level = df_vix['Close'].values[vix_idx]
            if btc_down:
                if vix_level > 30:
                    vix_score = +5
                    vix_signal = "🔴 Panic Sell Risk Assets (VIX>30 + BTC down)"
                elif vix_level >= 20:
                    vix_score = +3
                    vix_signal = "🟠 Fear Dragging BTC (VIX 20-30)"
                else:
                    vix_score = +1
                    vix_signal = "⚪ Calm Decline (VIX<20 + BTC down)"
            else:
                if vix_level > 30:
                    vix_score = 0
                    vix_signal = "⚪ BTC Resilient (VIX>30 + BTC up)"
                elif vix_level >= 20:
                    vix_score = -2
                    vix_signal = "🟢 Fear But BTC Up (VIX 20-30)"
                else:
                    vix_score = -3
                    vix_signal = "🟢 Risk-On Rally (VIX<20 + BTC up)"

    total_d6 = max(min(dxy_score + vix_score, 10), -10)
    d6_scaled = (total_d6 + 10) / 20 * 100

    return {
        'd6_total': total_d6, 'd6_scaled': d6_scaled,
        'dxy_score': dxy_score, 'vix_score': vix_score,
        'dxy_1m': dxy_1m, 'vix_level': vix_level,
        'dxy_signal': dxy_signal, 'vix_signal': vix_signal,
        'btc_1m': btc_1m
    }


# ══════════════════════════════════════════════════════
# SELL-SIDE PENALTY: Punishes BULLISH reversals
# ══════════════════════════════════════════════════════

def calc_sell_penalties(df, base_idx):
    closes = df['Close'].values
    ret_1y = compute_return(closes, base_idx, 252) or 0
    ret_6m = compute_return(closes, base_idx, 126) or 0
    ret_1m = compute_return(closes, base_idx, 21) or 0
    ret_1w = compute_return(closes, base_idx, 5) or 0

    reversal_pen = 0
    reversal_flag = ""
    strong = (ret_1y < -20 and ret_1m > 5 and ret_1w > 3)
    mild = ((ret_1y < 0 or ret_6m < 0) and ret_1m > 0 and ret_1w > 0)
    if strong:
        reversal_pen = -10
        reversal_flag = "🟢 Strong Bullish Reversal (bad for sell)"
    elif mild:
        reversal_pen = -5
        reversal_flag = "⚠️ Mild Bullish Reversal (bad for sell)"

    ma50 = calc_ma(df, base_idx, 50)
    ma200 = calc_ma(df, base_idx, 200)
    price = closes[base_idx]
    gc_pen = 0
    gc_flag = ""
    if ma50 is not None and ma200 is not None and ma50 > ma200:
        gc_pen = -5
        if price > ma50 and price > ma200:
            gc_flag = "✨✨ Golden Cross + Above MAs (bad for sell)"
        else:
            gc_flag = "✨ Golden Cross (bad for sell)"

    total = max(reversal_pen + gc_pen, -15)
    flags = " | ".join(f for f in [reversal_flag, gc_flag] if f)
    return {
        'reversal': reversal_pen, 'golden_cross_pen': gc_pen,
        'total': total, 'flags': flags,
        'ret_1y': ret_1y, 'ret_6m': ret_6m, 'ret_1m': ret_1m, 'ret_1w': ret_1w
    }


# ══════════════════════════════════════════════════════
# COMPUTE FULL SELL SCORES
# ══════════════════════════════════════════════════════

def full_sell_score(df, idx, df_dxy, df_vix):
    ret_pctls = calc_return_percentiles(df, idx)
    vol_pctls = calc_volume_percentiles(df, idx)
    wp_ret = weighted_percentile(ret_pctls)
    wp_vol = weighted_percentile(vol_pctls)
    
    d1 = d1_sell_score(wp_ret)
    ret_1m = compute_return(df['Close'].values, idx, 21) or 0
    d2 = d2_sell_score(wp_vol, ret_1m)
    rsi = calc_rsi(df, idx)
    d3 = d3_sell_score(rsi)
    price = df['Close'].values[idx]
    ma50 = calc_ma(df, idx, 50)
    ma200 = calc_ma(df, idx, 200)
    d4 = d4_sell_score(price, ma50, ma200)
    vol = calc_volatility(df, idx)
    d5 = d5_sell_score(vol)
    ext = calc_d6_sell_external(df, idx, df_dxy, df_vix)
    d6 = ext['d6_scaled']
    
    gross = (d1 + d2 + d3 + d4 + d5 + d6) / 6
    penalties = calc_sell_penalties(df, idx)
    penalty_scaled = penalties['total'] * (100 / 110)
    net = gross + penalty_scaled
    
    death_cross = (ma50 is not None and ma200 is not None and ma50 < ma200)
    golden_cross = (ma50 is not None and ma200 is not None and ma50 > ma200)
    
    return {
        'date': df.iloc[idx]['Date'], 'price': price,
        'ret_pctls': ret_pctls, 'vol_pctls': vol_pctls,
        'wp_ret': wp_ret, 'wp_vol': wp_vol,
        'd1': d1, 'd2': d2, 'd3': d3, 'd4': d4, 'd5': d5, 'd6': d6,
        'd6_raw': ext['d6_total'],
        'rsi': rsi, 'ma50': ma50, 'ma200': ma200,
        'death_cross': death_cross, 'golden_cross': golden_cross,
        'volatility': vol, 'gross': gross, 'penalties': penalties,
        'penalty_scaled': penalty_scaled, 'net': net, 'external': ext
    }


s1 = full_sell_score(df, BD1_idx, df_dxy, df_vix)
s2 = full_sell_score(df, BD2_idx, df_dxy, df_vix)

net_avg = (s1['net'] + s2['net']) / 2
gross_avg = (s1['gross'] + s2['gross']) / 2
delta = s2['net'] - s1['net']

def tier_sell(score):
    clamped = max(0, min(100, score))
    if clamped >= 85: return "Very Strong Sell ↓↓"
    if clamped >= 75: return "Strong Sell ↓"
    if clamped >= 60: return "Moderate Sell ↓"
    if clamped >= 45: return "Neutral →"
    if clamped >= 30: return "Weak Sell"
    return "No Sell Signal"

sell_tier = tier_sell(net_avg)

print(f"\n{'='*55}")
print(f"BTC SELL Momentum Score v3.0")
print(f"{'='*55}")
print(f"Sell Score Avg:  {net_avg:.2f}  ({sell_tier})")
print(f"Gross Score Avg: {gross_avg:.2f}")
print(f"BD1 ({s1['date'].strftime('%Y-%m-%d')}): Net={s1['net']:.2f}")
print(f"BD2 ({s2['date'].strftime('%Y-%m-%d')}): Net={s2['net']:.2f}")
print(f"Delta: {delta:+.2f}")
print(f"Price: ${s2['price']:.1f}")
print(f"D1s={s2['d1']:.1f}  D2s={s2['d2']:.1f}  D3s={s2['d3']:.1f}  D4s={s2['d4']:.1f}  D5s={s2['d5']:.1f}  D6s={s2['d6']:.1f}")
print(f"Penalties: {s2['penalties']['total']} (scaled: {s2['penalty_scaled']:.1f}) ({s2['penalties']['flags'] or 'None'})")


# ══════════════════════════════════════════════════════
# CSV OUTPUT — SELL
# ══════════════════════════════════════════════════════

csv_row = {
    'Rank': 1, 'Ticker': 'BTC', 'Side': 'SELL',
    'Net_Score_Avg': round(net_avg, 2),
    'Gross_Score_Avg': round(gross_avg, 2),
    'Net_Score_BD1': round(s1['net'], 2),
    'Net_Score_BD2': round(s2['net'], 2),
    'Score_Delta': round(delta, 2),
    'Tier': sell_tier,
    'D1_ReturnRank': round(s2['d1'], 2),
    'D2_VolumeRank': round(s2['d2'], 2),
    'D3_RSI': round(s2['d3'], 2),
    'D4_MA': round(s2['d4'], 2),
    'D5_Volatility': round(s2['d5'], 2),
    'D6_External': round(s2['d6'], 2),
    'D6_Raw': s2['d6_raw'],
    'Penalty_Scaled': round(s2['penalty_scaled'], 2),
    'WP_Return_Pct': round(s2['wp_ret'], 2),
    'WP_Volume_Pct': round(s2['wp_vol'], 2),
    'Ret_1Y_Pct': round(s2['penalties']['ret_1y'], 2),
    'Ret_6M_Pct': round(s2['penalties']['ret_6m'], 2),
    'Ret_3M_Pct': round(s2['ret_pctls']['3M']['return'], 2),
    'Ret_1M_Pct': round(s2['ret_pctls']['1M']['return'], 2),
    'Ret_1W_Pct': round(s2['ret_pctls']['1W']['return'], 2),
    'RSI_Value': round(s2['rsi'], 2),
    'MA50': round(s2['ma50'], 2) if s2['ma50'] else '',
    'MA200': round(s2['ma200'], 2) if s2['ma200'] else '',
    'Price': round(s2['price'], 2),
    'Death_Cross': str(s2['death_cross']),
    'Golden_Cross': str(s2['golden_cross']),
    'Volatility_Pct': round(s2['volatility'], 2),
    'Penalty_Total': s2['penalties']['total'],
    'Penalty_Reversal': s2['penalties']['reversal'],
    'Penalty_GoldenCross': s2['penalties']['golden_cross_pen'],
    'Warning_Flags': s2['penalties']['flags'] if s2['penalties']['flags'] else 'None',
    'DXY_1M_Pct': round(s2['external']['dxy_1m'], 2) if s2['external']['dxy_1m'] is not None else '',
    'VIX_Level': round(s2['external']['vix_level'], 2) if s2['external']['vix_level'] is not None else '',
    'DXY_Signal': s2['external']['dxy_signal'],
    'VIX_Signal': s2['external']['vix_signal'],
    'Base_Date_1': s1['date'].strftime('%Y-%m-%d'),
    'Base_Date_2': s2['date'].strftime('%Y-%m-%d'),
    'As_Of_Running': AS_OF,
}

csv_df = pd.DataFrame([csv_row])
csv_fixed = os.path.join(base_dir, 'output_momentum_btc_sell.csv')
csv_ts = os.path.join(base_dir, f'output_momentum_btc_sell_{TS_FILE}.csv')
csv_df.to_csv(csv_fixed, index=False, encoding='utf-8')
csv_df.to_csv(csv_ts, index=False, encoding='utf-8')
print(f"\nCSV saved: {csv_fixed}")
print(f"CSV saved: {csv_ts}")
print(f"\n✅ BTC SELL score outputs generated successfully!")
