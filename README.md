# kalshi-polymarket-arb

Real-time arbitrage detector across two prediction market platforms — [Kalshi](https://kalshi.com) and [Polymarket](https://polymarket.com). Maintains live orderbooks for both platforms via WebSocket and checks for cross-platform mispricings on the same underlying event.

## How it works

Prediction markets price binary outcomes (YES/NO) between $0 and $1. If the same event is listed on two platforms, the combined cost of buying complementary positions should be ≥ $1. When it isn't, there's a risk-free profit.

The arbitrage checker monitors four strategies per market pair (**note that Team2-YES is equivalent to Team1-NO on Polymarket but not on Kalshi**):

| Strategy | Buy | Buy |
|----------|-----|-----|
| 1 | Polymarket Team1-YES | Kalshi Team1-NO |
| 2 | Polymarket Team1-YES | Kalshi Team2-YES |
| 3 | Polymarket Team2-YES | Kalshi Team2-NO |
| 4 | Polymarket Team2-YES | Kalshi Team1-YES |

Each platform streams orderbook updates via WebSocket. The checker subscribes to both, maintains the full orderbook state in memory, and evaluates all four strategies on every update.

## Project structure

```
kalshi-polymarket-arb/
├── realtime/
│   ├── arbitrage_checker.py          # Main entry point
│   ├── kalshi_realtime_orderbook.py  # Standalone Kalshi orderbook viewer
│   └── polymarket_realtime_orderbook.py
├── orderbook/
│   ├── Kalshi/kalshi_orderbook.py    # Kalshi WS client + orderbook state
│   ├── Polymarket/polymarket_orderbook.py
│   └── Utility/                      # Plotting and data processing tools
└── config_paths.py                   # Credential file resolution
```

## Setup

Requires Python 3.11+. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first, then:

```
uv sync
```

### Credentials

Kalshi uses RSA key authentication. Save your credentials at the repo root (both are gitignored):
- `kalshi_api.txt` — your API key ID
- `kalshi_private_key.pem` — your RSA private key

See [KALSHI_AUTH_SETUP.md](KALSHI_AUTH_SETUP.md) for detailed instructions.

## Running

**Arbitrage checker** (monitors both platforms, prints opportunities):
```
uv run python realtime/arbitrage_checker.py
```

**Standalone orderbook viewers** (display live orderbook in terminal):
```
uv run python realtime/kalshi_realtime_orderbook.py
uv run python realtime/polymarket_realtime_orderbook.py
```

Update the `TICKERS` list at the top of each script to the markets you want to watch.

## Notes

- Kalshi prices are in cents (1–99), Polymarket in decimals (0.01–0.99) — the checker normalizes both to decimals before comparison
- Orderbook deltas fire on any book change (new order, cancel, fill) — not just trades
- The checker prints to stdout on every update; wire in your own execution logic to act on opportunities (including wiring fee structure)
