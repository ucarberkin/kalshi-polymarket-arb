"""
Simple WebSocket client for Kalshi.
Subscribes to orderbook deltas and displays all messages.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import time, base64, asyncio, websockets, json
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
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


async def connect():
    """Connect to Kalshi WebSocket and subscribe to tickers."""
    async with websockets.connect(WS_HOST + WS_PATH, additional_headers=ws_headers()) as ws:
        print("Connected to Kalshi WebSocket")

        # Subscribe to all available channels for all tickers in one message
        # Available: ticker, orderbook_delta
        subscription = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["ticker", "orderbook_delta"],
                "market_tickers": TICKERS
            }
        }
        await ws.send(json.dumps(subscription))
        print(f"Subscribed to: {TICKERS}")

        print("\nReceiving messages (Ctrl+C to stop)...\n")

        # Receive and print messages
        while True:
            msg = await ws.recv()
            print("=" * 80)
            try:
                print(json.dumps(json.loads(msg), indent=2))
            except:
                print(msg)
            print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(connect())
    except KeyboardInterrupt:
        print("\nDisconnected.")
