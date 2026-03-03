# Pump.fun Experimental Tests

This folder contains **experimental code** for testing bonding curve formulas and building synthetic orderbook depth calculators.

**WARNING**: Code in this folder is NOT production-ready. It's for research and validation only.

## Current Experiments

### 1. Bonding Curve Formula Validation (`test_bonding_curve_formula.py`)

**Purpose**: Empirically test if the bonding curve formula from the Binance Square post is accurate.

**Formula being tested**:
```
y = 1073000191 - 32190005730/(30+x)
```

Where:
- `x` = cumulative SOL purchased
- `y` = tokens obtained

**How to run**:
```bash
python test_bonding_curve_formula.py
```

**What it does**:
1. Connects to pump.fun WebSocket
2. Subscribes to a token's trades
3. Collects trades for 30 seconds
4. Calculates predicted vs actual token amounts
5. Reports accuracy statistics

**Expected output**:
- Average error percentage
- Accuracy distribution (< 1%, < 5% error)
- Sample trade comparisons
- Overall conclusion on formula accuracy

**Next steps after validation**:
- If accurate (< 5% error): Build synthetic depth calculator
- If inaccurate: Fall back to trade-only data collection

## Why Experimental?

We don't have official pump.fun documentation for the bonding curve. The formula comes from:
- Source: Binance Square user post
- Method: Claimed "front-end code analysis"
- Status: Unverified

This experimental validation helps us determine if it's safe to use for production orderbook construction.

## Production Code Location

Once validated, production code will live in:
- `/orderbook/Pump.fun/pumpfun_orderbook.py` (if formula is accurate)
- `/data/ingest/connectors/pumpfun_ws_connector.py` (for data pipeline)
