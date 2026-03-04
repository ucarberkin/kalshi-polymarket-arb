"""
Simple real-time orderbook viewer for Polymarket.

Maintains full orderbook (all price levels) and displays updates in real-time.
- book events: Full orderbook snapshot (replaces everything)
- price_change events: Update specific price level (replace size at that price)
"""
import json
import websocket
from datetime import datetime
from collections import OrderedDict

# Configuration
# Replace asset IDs with current events you want to observe
ASSET_IDS = [
    "32032245236655318400797290255881067171693430317457825461889587709601561202503",
    "109081243913383015615425037992636571273513271639233491652524900113026919029196"
]

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Full orderbook state: asset_id -> {"bids": {price: size}, "asks": {price: size}}
orderbooks = {}


def display_orderbook(asset_id, event_type):
    """Display the current orderbook for an asset."""
    if asset_id not in orderbooks:
        return

    ob = orderbooks[asset_id]
    bids = ob.get("bids", {})
    asks = ob.get("asks", {})

    # Sort bids descending (highest first), asks ascending (lowest first)
    sorted_bids = sorted(bids.items(), key=lambda x: float(x[0]), reverse=True)
    sorted_asks = sorted(asks.items(), key=lambda x: float(x[0]))

    print(f"\n{'='*80}")
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {event_type.upper()} UPDATE")
    print(f"Asset: {asset_id[:12]}...")
    print(f"{'='*80}")

    # Show top 10 levels
    print(f"\n{'BIDS':<40} | {'ASKS':<40}")
    print(f"{'-'*40} | {'-'*40}")

    max_rows = max(len(sorted_bids[:10]), len(sorted_asks[:10]))

    for i in range(max_rows):
        # Bid side
        if i < len(sorted_bids):
            bid_price, bid_size = sorted_bids[i]
            bid_str = f"{bid_price:>10} @ {bid_size:<15}"
        else:
            bid_str = " " * 40

        # Ask side
        if i < len(sorted_asks):
            ask_price, ask_size = sorted_asks[i]
            ask_str = f"{ask_price:>10} @ {ask_size:<15}"
        else:
            ask_str = " " * 40

        print(f"{bid_str} | {ask_str}")

    print(f"\nTotal levels: {len(bids)} bids, {len(asks)} asks")
    print(f"{'='*80}")


def process_book_event(message):
    """Process 'book' event - full orderbook snapshot."""
    asset_id = message.get("asset_id")
    if not asset_id:
        return

    # Initialize orderbook for this asset
    if asset_id not in orderbooks:
        orderbooks[asset_id] = {"bids": {}, "asks": {}}

    # Replace entire orderbook
    orderbooks[asset_id]["bids"] = {}
    orderbooks[asset_id]["asks"] = {}

    # Populate bids
    for bid in message.get("bids", []):
        price = bid.get("price")
        size = bid.get("size")
        if price and size:
            orderbooks[asset_id]["bids"][price] = size

    # Populate asks
    for ask in message.get("asks", []):
        price = ask.get("price")
        size = ask.get("size")
        if price and size:
            orderbooks[asset_id]["asks"][price] = size

    # Display updated orderbook
    display_orderbook(asset_id, "book")


def process_price_change_event(message):
    """Process 'price_change' event - update specific price level."""
    price_changes = message.get("price_changes", [])

    for change in price_changes:
        asset_id = change.get("asset_id")
        if not asset_id:
            continue

        # Initialize orderbook if needed
        if asset_id not in orderbooks:
            orderbooks[asset_id] = {"bids": {}, "asks": {}}

        price = change.get("price")
        size = change.get("size")
        side = change.get("side")  # "BUY" or "SELL"

        if not price or not size or not side:
            continue

        # Update the specific price level (REPLACE size, not add/subtract)
        if side == "BUY":
            if float(size) == 0:
                # Remove the level if size is 0
                orderbooks[asset_id]["bids"].pop(price, None)
            else:
                # Replace/add the level
                orderbooks[asset_id]["bids"][price] = size
        elif side == "SELL":
            if float(size) == 0:
                # Remove the level if size is 0
                orderbooks[asset_id]["asks"].pop(price, None)
            else:
                # Replace/add the level
                orderbooks[asset_id]["asks"][price] = size

        # Display updated orderbook
        display_orderbook(asset_id, "price_change")


def on_message(ws, message):
    """Handle incoming WebSocket messages."""
    # Skip control messages
    if message.strip() in ["PONG", "PING"]:
        return

    try:
        data = json.loads(message)

        # Handle both single dict and array of messages
        messages = [data] if isinstance(data, dict) else data if isinstance(data, list) else []

        for msg in messages:
            if not isinstance(msg, dict):
                continue

            event_type = msg.get("event_type")

            if event_type == "book":
                process_book_event(msg)
            elif event_type == "price_change":
                process_price_change_event(msg)
            # Ignore other event types

    except Exception as e:
        print(f"Error processing message: {e}")


def on_error(ws, error):
    """Print errors."""
    print(f"\nERROR: {error}")


def on_close(ws, close_status_code, close_msg):
    """Print close info."""
    print(f"\nConnection closed: {close_status_code} - {close_msg}")


def on_open(ws):
    """Subscribe to assets when connection opens."""
    print(f"Connected to {WS_URL}")

    subscription = {
        "assets_ids": ASSET_IDS,
        "type": "market"
    }

    ws.send(json.dumps(subscription))
    print(f"Subscribed to {len(ASSET_IDS)} assets")
    print("\nWaiting for orderbook updates...\n")


if __name__ == "__main__":
    print("="*80)
    print("POLYMARKET REAL-TIME ORDERBOOK VIEWER")
    print("="*80)
    print(f"Assets: {len(ASSET_IDS)}")
    for i, asset_id in enumerate(ASSET_IDS, 1):
        print(f"  {i}. {asset_id[:20]}...")
    print("="*80 + "\n")

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
