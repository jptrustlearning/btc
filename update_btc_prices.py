#!/usr/bin/env python3
"""
🪙 BTC/USDT Daily OHLCV Updater
JP Trust Learning

ดึงข้อมูลราคา BTC รายวัน — ลอง Binance API ก่อน, ถ้าไม่ได้ fallback เป็น yfinance
Merge กับข้อมูลเดิมใน btc_prices.csv แล้วบันทึก

Usage:
    python3 update_btc_prices.py              # Update ข้อมูลล่าสุด
    python3 update_btc_prices.py --backfill   # ดึงข้อมูลย้อนหลังทั้งหมด (ตั้งแต่ 2017)
    python3 update_btc_prices.py --source binance   # บังคับใช้ Binance
    python3 update_btc_prices.py --source yfinance  # บังคับใช้ yfinance
"""

import pandas as pd
import os
import sys
from datetime import datetime, timedelta, timezone

# =============================================================================
# CONFIG
# =============================================================================
CSV_FILE = "btc_prices.csv"
BACKFILL_START = datetime(2017, 8, 17, tzinfo=timezone.utc)

# Column names (Thai headers เหมือน gold repo)
THAI_COLUMNS = ['วันที่', 'ราคาเปิด', 'ราคาสูงสุด', 'ราคาต่ำสุด', 'ราคาปิด', 'ปริมาณซื้อขาย']
ENG_COLUMNS = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']


# =============================================================================
# SOURCE 1: Binance API (primary — ใช้ใน GitHub Actions)
# =============================================================================
def fetch_binance(start_date):
    """ดึง BTC/USDT daily OHLCV จาก Binance API"""
    import requests
    
    BINANCE_API = "https://api.binance.com/api/v3/klines"
    all_data = []
    start_ms = int(start_date.timestamp() * 1000)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    print(f"📊 [Binance] Fetching BTCUSDT 1d from {start_date.date()} ...")
    
    while start_ms < now_ms:
        params = {
            'symbol': 'BTCUSDT',
            'interval': '1d',
            'startTime': start_ms,
            'limit': 1000
        }
        response = requests.get(BINANCE_API, params=params, timeout=30)
        response.raise_for_status()
        klines = response.json()
        
        if not klines:
            break
        
        for k in klines:
            open_time = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc)
            all_data.append({
                'Date': open_time.strftime('%Y-%m-%d'),
                'Open': round(float(k[1]), 1),
                'High': round(float(k[2]), 1),
                'Low': round(float(k[3]), 1),
                'Close': round(float(k[4]), 1),
                'Volume': round(float(k[5]), 4)
            })
        
        last_open_time = klines[-1][0]
        start_ms = last_open_time + 1
        print(f"  → {len(klines)} candles, latest: {all_data[-1]['Date']}")
        
        if len(klines) < 1000:
            break
    
    if all_data:
        return pd.DataFrame(all_data)
    return pd.DataFrame(columns=ENG_COLUMNS)


# =============================================================================
# SOURCE 2: yfinance (fallback — ใช้เมื่อ Binance ไม่ได้)
# =============================================================================
def fetch_yfinance(start_date):
    """ดึง BTC-USD daily OHLCV จาก Yahoo Finance"""
    import yfinance as yf
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    print(f"📊 [yfinance] Fetching BTC-USD from {start_str} to {end_str} ...")
    
    ticker = yf.Ticker("BTC-USD")
    df = ticker.history(start=start_str, end=end_str, interval="1d")
    
    if df.empty:
        return pd.DataFrame(columns=ENG_COLUMNS)
    
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].reset_index()
    
    # Handle timezone
    if hasattr(df['Date'].dtype, 'tz') and df['Date'].dt.tz is not None:
        df['Date'] = df['Date'].dt.tz_localize(None)
    
    df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    for col in ['Open', 'High', 'Low', 'Close']:
        df[col] = df[col].round(1)
    df['Volume'] = df['Volume'].round(4)
    
    print(f"  → {len(df)} candles fetched")
    return df


# =============================================================================
# MAIN
# =============================================================================
def main():
    backfill = '--backfill' in sys.argv
    
    # Determine source preference
    force_source = None
    if '--source' in sys.argv:
        idx = sys.argv.index('--source')
        if idx + 1 < len(sys.argv):
            force_source = sys.argv[idx + 1]
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, CSV_FILE)
    
    # ===== อ่านข้อมูลเดิม =====
    if os.path.exists(csv_path) and not backfill:
        df_existing = pd.read_csv(csv_path, encoding='utf-8-sig')
        df_existing.columns = ENG_COLUMNS
        df_existing['Date'] = pd.to_datetime(df_existing['Date'])
        last_date = df_existing['Date'].max()
        start_date = (last_date + timedelta(days=1)).replace(tzinfo=timezone.utc)
        print(f"📂 Existing: {len(df_existing)} rows, last: {last_date.date()}")
    else:
        df_existing = pd.DataFrame(columns=ENG_COLUMNS)
        start_date = BACKFILL_START
        if backfill:
            print(f"🔄 Backfill mode: fetching from {BACKFILL_START.date()}")
        else:
            print(f"📂 No existing file — backfilling from {BACKFILL_START.date()}")
    
    # ===== ดึงข้อมูลใหม่ =====
    now_utc = datetime.now(timezone.utc)
    if start_date.date() >= now_utc.date():
        print("\nℹ️  Already up to date — nothing to fetch")
        return
    
    df_new = pd.DataFrame(columns=ENG_COLUMNS)
    
    if force_source == 'yfinance':
        df_new = fetch_yfinance(start_date)
    elif force_source == 'binance':
        df_new = fetch_binance(start_date)
    else:
        # Auto: try Binance first, fallback to yfinance
        try:
            df_new = fetch_binance(start_date)
        except Exception as e:
            print(f"⚠️  Binance failed: {e}")
            print("🔄 Falling back to yfinance ...")
            try:
                df_new = fetch_yfinance(start_date)
            except Exception as e2:
                print(f"❌ yfinance also failed: {e2}")
                return
    
    if df_new.empty:
        print("\nℹ️  No new data available")
        return
    
    # ===== Filter: ไม่เอาวันนี้ (candle ยังไม่ปิด) =====
    today_str = now_utc.strftime('%Y-%m-%d')
    df_new = df_new[df_new['Date'] != today_str]
    
    if df_new.empty:
        print("\nℹ️  No completed candles to add (today's candle still open)")
        return
    
    new_count = len(df_new)
    
    # ===== Merge =====
    df_new['Date'] = pd.to_datetime(df_new['Date'])
    df_all = pd.concat([df_existing, df_new], ignore_index=True)
    df_all = df_all.drop_duplicates(subset='Date', keep='last')
    df_all = df_all.sort_values('Date').reset_index(drop=True)
    
    # ===== Save (Thai headers เหมือน gold repo) =====
    df_out = df_all.copy()
    df_out['Date'] = df_out['Date'].dt.strftime('%Y-%m-%d')
    df_out.columns = THAI_COLUMNS
    df_out.to_csv(csv_path, index=False, encoding='utf-8-sig')
    
    latest_price = df_all['Close'].iloc[-1]
    latest_date = df_all['Date'].max().strftime('%Y-%m-%d')
    
    print(f"\n{'='*50}")
    print(f"✅ Saved: {len(df_all)} total rows")
    print(f"📅 Range: {df_all['Date'].min().date()} → {df_all['Date'].max().date()}")
    print(f"🏷️  Latest: ${latest_price:,.1f} @ {latest_date}")
    print(f"📊 New rows added: +{new_count}")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
