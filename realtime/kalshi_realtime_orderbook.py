"""
Real-time orderbook viewer for Kalshi.
Maintains and displays orderbook state with each update.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time, base64, asyncio, websockets, json
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from collections import defaultdict
from config_paths import read_secret_text, read_secret_bytes

# Configuration
# Replace with active Kalshi market tickers (find them at kalshi.com/markets)
TICKERS = [
    "kxnbagame-26mar03detcle-det",
    "kxnbagame-26mar03detcle-cle"
]
TICKERS = [t.upper() for t in TICKERS]

# Kalshi API
WS_HOST = "wss://api.elections.kalshi.com"
WS_PATH = "/trade-api/ws/v2"

# Load credentials
KEY_ID = read_secret_text("kalshi_api.txt", env_var="KALSHI_API_FILE")
raw = read_secret_bytes("kalshi_private_key.pem", env_var="KALSHI_PRIVATE_KEY_FILE")
if b"\\n" in raw and b"\n" not in raw:
    raw = raw.replace(b"\\n", b"\n")
priv = serialization.load_pem_private_key(raw, password=None)

# Orderbook storage: {market_ticker: {"yes": {price: size, ...}, "no": {price: size, ...}}}
orderbooks = defaultdict(lambda: {"yes": {}, "no": {}})


def ws_headers():
    """Generate authentication headers for WebSocket connection."""
    ts = str(int(time.time() * 1000))
    to_sign = f"{ts}GET{WS_PATH}".encode()
    sig = priv.sign(
        to_sign,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }


def process_orderbook_snapshot(data):
    """Process full orderbook snapshot - replace entire orderbook."""
    msg = data.get("msg", {})
    ticker = msg.get("market_ticker")

    if not ticker:
        return

    # Clear and rebuild orderbook
    orderbooks[ticker]["yes"] = {}
    orderbooks[ticker]["no"] = {}

    # Process yes side (each entry is [price, size])
    for price, size in msg.get("yes", []):
        if size > 0:
            orderbooks[ticker]["yes"][price] = size

    # Process no side
    for price, size in msg.get("no", []):
        if size > 0:
            orderbooks[ticker]["no"][price] = size

    print(f"\n{'='*80}")
    print(f"ORDERBOOK SNAPSHOT: {ticker}")
    display_orderbook(ticker)


def process_orderbook_delta(data):
    """Process orderbook delta - update specific price levels."""
    msg = data.get("msg", {})
    ticker = msg.get("market_ticker")

    if not ticker:
        return

    price = msg.get("price")
    delta = msg.get("delta")
    side = msg.get("side")

    if price is None or delta is None or side not in ["yes", "no"]:
        return

    current_size = orderbooks[ticker][side].get(price, 0)
    new_size = current_size + delta

    if new_size <= 0:
        orderbooks[ticker][side].pop(price, None)
    else:
        orderbooks[ticker][side][price] = new_size

    print(f"\n{'='*80}")
    print(f"ORDERBOOK UPDATE: {ticker}")
    display_orderbook(ticker)


def display_orderbook(ticker, depth=10):
    """Display top N levels of orderbook."""
    book = orderbooks[ticker]

    # Sort yes side (descending price)
    yes_levels = sorted(book["yes"].items(), key=lambda x: x[0], reverse=True)[:depth]

    # Sort no side (descending price)
    no_levels = sorted(book["no"].items(), key=lambda x: x[0], reverse=True)[:depth]

    print(f"\n{'YES SIDE':<30} | {'NO SIDE':<30}")
    print(f"{'Price':<10} {'Size':<18} | {'Price':<10} {'Size':<18}")
    print("-" * 63)

    # Display both sides side by side
    max_rows = max(len(yes_levels), len(no_levels))
    for i in range(max_rows):
        # Yes side
        if i < len(yes_levels):
            price, size = yes_levels[i]
            yes_str = f"{price:<10} {size:<18}"
        else:
            yes_str = " " * 28

        # No side
        if i < len(no_levels):
            price, size = no_levels[i]
            no_str = f"{price:<10} {size:<18}"
        else:
            no_str = " " * 28

        print(f"{yes_str} | {no_str}")

    print(f"\nTotal YES levels: {len(book['yes'])}, Total NO levels: {len(book['no'])}")
    print("="*80)


async def connect():
    """Connect to Kalshi WebSocket and maintain real-time orderbook."""
    async with websockets.connect(WS_HOST + WS_PATH, additional_headers=ws_headers()) as ws:
        print("Connected to Kalshi WebSocket")

        # Subscribe to orderbook deltas for all tickers in one message
        subscription = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_tickers": TICKERS
            }
        }
        await ws.send(json.dumps(subscription))
        print(f"Subscribed to: {TICKERS}")

        print("\nReceiving and processing orderbook updates (Ctrl+C to stop)...\n")

        # Process messages
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            msg_type = data.get("type")

            if msg_type == "orderbook_snapshot":
                process_orderbook_snapshot(data)
            elif msg_type == "orderbook_delta":
                process_orderbook_delta(data)
            # Ignore other message types (subscribed, error, etc.)


if __name__ == "__main__":
    try:
        asyncio.run(connect())
    except KeyboardInterrupt:
        print("\n\nDisconnected.")
