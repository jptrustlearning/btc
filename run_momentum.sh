#!/bin/bash
# BTC Momentum Score — Runner Script
# JP Trust Learning
# Usage: bash run_momentum.sh

set -e

cd "$(dirname "$0")"

echo "🪙 BTC Momentum Scoring v3.0"
echo "==============================="

# Pull latest data
echo "📥 Pulling latest data..."
git pull origin main || true

# Run all 3 scripts in order
echo ""
echo "▶ Running Buy Score..."
python3 btc_momentum_buy.py

echo ""
echo "▶ Running Sell Score..."
python3 btc_momentum_sell.py

echo ""
echo "▶ Running Net Bias..."
python3 btc_momentum_net.py

# Git push
echo ""
echo "📤 Pushing to GitHub..."
TIMESTAMP=$(date -u +"%d%m%Y_%H%M")
RUN_DISPLAY=$(date -u +"%d/%m/%Y %H:%M UTC")

git add output_momentum_btc*.csv
git add dxy_prices.csv vix_prices.csv 2>/dev/null || true
git commit -m "🪙 BTC Momentum Score v3.0 — ${RUN_DISPLAY}" || echo "Nothing to commit"
git push origin main || echo "Push failed — check credentials"

echo ""
echo "✅ Done!"
