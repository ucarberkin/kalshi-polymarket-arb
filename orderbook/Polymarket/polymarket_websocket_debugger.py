"""
Simple WebSocket client for Polymarket - ALL EVENTS.
Connects, subscribes, and displays everything the server sends.
No filtering, no processing - just raw messages.
"""
import json
import websocket

# Configuration
# Replace asset IDs with current events you want to observe
ASSET_IDS = [
    "77881334070158577463740854467727307173575468948786502140173574411480703129393",
    "34349145000138305620572837247044801454833792285183717557241049301550895642708"
]

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def on_message(ws, message):
    """Print whatever the server sends - no filtering."""
    print("\n" + "="*80)

    # Try to pretty-print if it's JSON, otherwise just print raw
    try:
        data = json.loads(message)
        print(json.dumps(data, indent=2))
    except:
        # Not JSON, print as-is
        print(message)

    print("="*80)


def on_error(ws, error):
    """Print errors."""
    print(f"\nERROR: {error}")


def on_close(ws, close_status_code, close_msg):
    """Print close info."""
    print(f"\nConnection closed: {close_status_code} - {close_msg}")


def on_open(ws):
    """Subscribe to assets when connection opens."""
    print(f"Connected to {WS_URL}")

    # Send subscription message
    subscription = {
        "assets_ids": ASSET_IDS,
        "type": "market"
    }

    ws.send(json.dumps(subscription))
    print(f"Subscribed to {len(ASSET_IDS)} assets")
    print("\nDisplaying ALL messages (book, price_change, etc.)...")
    print("Press Ctrl+C to stop\n")


if __name__ == "__main__":
    print("="*80)
    print("SIMPLE WEBSOCKET VIEWER - ALL EVENTS (NO FILTERING)")
    print("="*80)
    print(f"Assets: {len(ASSET_IDS)}")
    for i, asset_id in enumerate(ASSET_IDS, 1):
        print(f"  {i}. {asset_id[:20]}...")
    print("="*80 + "\n")

    # Create and run WebSocket
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    try:
        ws.run_forever()
    except KeyboardInterrupt:
        print("\n\nStopping...")
        ws.close()
