# 🪙 BTC/USDT Daily OHLCV
## JP Trust Learning — Auto-Updated via Binance API + GitHub Actions

ข้อมูลราคา Bitcoin (BTC/USDT) รายวัน — ดึงจาก Binance API อัตโนมัติ

---

## 📊 Data

| Item | Detail |
|------|--------|
| **Symbol** | BTC/USDT (Binance Spot) |
| **Interval** | Daily (1d) |
| **Range** | 17 Aug 2017 — ปัจจุบัน |
| **Update** | ทุกวัน 00:30 UTC (07:30 ไทย) อัตโนมัติ |
| **Format** | CSV, UTF-8 with BOM |
| **Source** | Binance API (primary), yfinance (fallback) |

### CSV Columns

```
วันที่,ราคาเปิด,ราคาสูงสุด,ราคาต่ำสุด,ราคาปิด,ปริมาณซื้อขาย
2017-08-17,4261.5,4485.4,4200.7,4285.1,795.15
```

| Column (Thai) | Column (English) | Description |
|--------------|-------------------|-------------|
| วันที่ | Date | YYYY-MM-DD |
| ราคาเปิด | Open | Opening price (USD) |
| ราคาสูงสุด | High | Highest price (USD) |
| ราคาต่ำสุด | Low | Lowest price (USD) |
| ราคาปิด | Close | Closing price (USD) |
| ปริมาณซื้อขาย | Volume | Volume (BTC) |

---

## 🔄 Auto-Update

GitHub Actions รันทุกวัน:
1. ดึงข้อมูลใหม่จาก Binance API
2. Merge กับข้อมูลเดิม (ไม่ซ้ำ)
3. บันทึก + Push กลับ repo

สามารถกด **Run workflow** ด้วยมือได้จาก Actions tab

### Backfill

รันครั้งแรกด้วย backfill=true เพื่อดึงข้อมูลย้อนหลังทั้งหมดตั้งแต่ 2017:
- Actions tab → Run workflow → เลือก backfill = true

---

## 📥 Usage

### Raw URL (ใช้ใน HTML / JavaScript)
```
https://raw.githubusercontent.com/jptrustlearning/btc/main/btc_prices.csv
```

### Python
```python
import pandas as pd

url = 'https://raw.githubusercontent.com/jptrustlearning/btc/main/btc_prices.csv'
df = pd.read_csv(url, encoding='utf-8-sig')
df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
df['Date'] = pd.to_datetime(df['Date'])
```

### JavaScript
```javascript
fetch('https://raw.githubusercontent.com/jptrustlearning/btc/main/btc_prices.csv')
  .then(r => r.text())
  .then(csv => {
    const lines = csv.split('\n').slice(1); // skip header
    const data = lines.filter(l => l.trim()).map(l => {
      const [date, open, high, low, close, volume] = l.split(',');
      return { date, open: +open, high: +high, low: +low, close: +close, volume: +volume };
    });
    console.log(`${data.length} rows, latest: $${data.at(-1).close}`);
  });
```

---

## 📁 Files

```
jptrustlearning/btc/
├── .github/workflows/
│   └── update_btc_prices.yml   ← GitHub Actions (daily auto-update)
├── btc_prices.csv               ← ข้อมูลราคา BTC (auto-updated)
├── update_btc_prices.py         ← Script ดึงข้อมูล (Binance + yfinance fallback)
└── README.md
```

---

## 🔑 Data Source

### Binance API (Primary)
```
GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1000
```
- ฟรี ไม่ต้องใช้ API key
- OHLCV ครบ + Volume เป็น BTC
- Candle ปิดที่ 00:00 UTC ทุกวัน

### yfinance (Fallback)
```python
yf.Ticker("BTC-USD").history(interval="1d")
```
- ใช้เมื่อ Binance API ไม่ตอบ
- Volume เป็น USD (แทน BTC)

---

*Created by JP TRUST LEARNING*
