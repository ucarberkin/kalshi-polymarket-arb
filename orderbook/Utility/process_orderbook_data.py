"""
Orderbook Data Processor

Reads raw WebSocket messages from JSON Lines files and reconstructs the full
orderbook state, saving snapshots to Parquet format.

Process:
1. Read raw .jsonl files from polymarket_raw_data/
2. Process messages chronologically
3. Maintain full orderbook state (all price levels)
4. Save orderbook snapshots to parquet files

Focus: Code clarity and data quality over efficiency
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import argparse


class OrderbookProcessor:
    """
    Processes raw WebSocket data to reconstruct orderbook state.

    Maintains a complete orderbook for each asset, updating it with:
    - 'book' events: Full orderbook replacement
    - 'price_change' events: Individual price level updates
    """

    def __init__(self, raw_data_dir: str = "./polymarket_raw_data",
                 processed_data_dir: str = "./polymarket_processed_data"):
        """
        Initialize the processor.

        Args:
            raw_data_dir: Directory containing raw .jsonl files
            processed_data_dir: Directory to save processed parquet files
        """
        self.raw_data_dir = Path(raw_data_dir)
        self.processed_data_dir = Path(processed_data_dir)
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)

        # Orderbook state: asset_id -> {"bids": {price: size}, "asks": {price: size}}
        self.orderbooks: Dict[str, Dict[str, Dict[str, str]]] = {}

        # Collect snapshots for each asset
        self.snapshots: Dict[str, List[Dict]] = {}

        # Statistics
        self.messages_processed = 0
        self.book_events = 0
        self.price_change_events = 0

    def process_book_event(self, message: dict, received_at: str):
        """
        Process a 'book' event - full orderbook snapshot.

        Args:
            message: The book event message
            received_at: Timestamp when message was received
        """
        asset_id = message.get("asset_id")
        if not asset_id:
            return

        # Initialize orderbook for this asset if needed
        if asset_id not in self.orderbooks:
            self.orderbooks[asset_id] = {"bids": {}, "asks": {}}
            self.snapshots[asset_id] = []

        # Replace entire orderbook with snapshot
        self.orderbooks[asset_id]["bids"] = {}
        self.orderbooks[asset_id]["asks"] = {}

        # Populate bids
        for bid in message.get("bids", []):
            price = bid.get("price")
            size = bid.get("size")
            if price and size:
                self.orderbooks[asset_id]["bids"][price] = size

        # Populate asks
        for ask in message.get("asks", []):
            price = ask.get("price")
            size = ask.get("size")
            if price and size:
                self.orderbooks[asset_id]["asks"][price] = size

        # Create snapshot
        self.save_snapshot(asset_id, received_at, message.get("timestamp"), "book")
        self.book_events += 1

    def process_price_change_event(self, message: dict, received_at: str):
        """
        Process a 'price_change' event - individual order update.

        Args:
            message: The price_change event message
            received_at: Timestamp when message was received
        """
        price_changes = message.get("price_changes", [])

        for change in price_changes:
            asset_id = change.get("asset_id")
            if not asset_id:
                continue

            # Initialize orderbook if needed
            if asset_id not in self.orderbooks:
                self.orderbooks[asset_id] = {"bids": {}, "asks": {}}
                self.snapshots[asset_id] = []

            price = change.get("price")
            size = change.get("size")
            side = change.get("side")  # "BUY" or "SELL"

            if not price or size is None or not side:
                continue

            # Update the specific price level (REPLACE size)
            if side == "BUY":
                if float(size) == 0:
                    # Remove the level if size is 0
                    self.orderbooks[asset_id]["bids"].pop(price, None)
                else:
                    # Replace/add the level
                    self.orderbooks[asset_id]["bids"][price] = size
            elif side == "SELL":
                if float(size) == 0:
                    # Remove the level if size is 0
                    self.orderbooks[asset_id]["asks"].pop(price, None)
                else:
                    # Replace/add the level
                    self.orderbooks[asset_id]["asks"][price] = size

            # Create snapshot
            self.save_snapshot(asset_id, received_at, message.get("timestamp"), "price_change")

        self.price_change_events += 1

    def save_snapshot(self, asset_id: str, received_at: str,
                      exchange_timestamp: Optional[int], event_type: str):
        """
        Save current orderbook state as a snapshot.

        Args:
            asset_id: The asset identifier
            received_at: ISO timestamp when we received the message
            exchange_timestamp: Exchange's timestamp (milliseconds)
            event_type: Type of event that triggered this snapshot
        """
        orderbook = self.orderbooks[asset_id]

        # Get sorted bids and asks
        bids = sorted(orderbook["bids"].items(),
                     key=lambda x: float(x[0]), reverse=True)
        asks = sorted(orderbook["asks"].items(),
                     key=lambda x: float(x[0]))

        # Create snapshot record
        snapshot = {
            "received_at": received_at,
            "exchange_timestamp": exchange_timestamp,
            "event_type": event_type,
            "asset_id": asset_id,
            "num_bid_levels": len(bids),
            "num_ask_levels": len(asks),
            "bids": bids,  # List of (price, size) tuples
            "asks": asks,  # List of (price, size) tuples
        }

        # Add best bid/ask for convenience
        if bids:
            snapshot["best_bid_price"] = float(bids[0][0])
            snapshot["best_bid_size"] = float(bids[0][1])
        else:
            snapshot["best_bid_price"] = None
            snapshot["best_bid_size"] = None

        if asks:
            snapshot["best_ask_price"] = float(asks[0][0])
            snapshot["best_ask_size"] = float(asks[0][1])
        else:
            snapshot["best_ask_price"] = None
            snapshot["best_ask_size"] = None

        self.snapshots[asset_id].append(snapshot)

    def process_file(self, filepath: Path):
        """
        Process a single .jsonl file.

        Args:
            filepath: Path to the .jsonl file
        """
        print(f"\nProcessing: {filepath.name}")
        file_messages = 0

        with open(filepath, 'r') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    # Parse the line
                    data = json.loads(line)
                    received_at = data.get("received_at")
                    message = data.get("message")

                    if not message:
                        continue

                    # Process based on event type
                    event_type = message.get("event_type")

                    if event_type == "book":
                        self.process_book_event(message, received_at)
                    elif event_type == "price_change":
                        self.process_price_change_event(message, received_at)
                    # Ignore other event types

                    file_messages += 1
                    self.messages_processed += 1

                    # Progress indicator
                    if file_messages % 1000 == 0:
                        print(f"  Processed {file_messages:,} messages...", end='\r')

                except Exception as e:
                    print(f"\n  Warning: Error on line {line_num}: {e}")
                    continue

        print(f"  Processed {file_messages:,} messages from {filepath.name}")

    def save_to_parquet(self):
        """
        Save all snapshots to parquet files (one per asset).
        """
        print("\nSaving to Parquet files...")

        for asset_id, snapshots in self.snapshots.items():
            if not snapshots:
                continue

            # Convert snapshots to DataFrame
            # We'll flatten the bids/asks arrays for parquet storage
            records = []

            for snapshot in snapshots:
                record = {
                    "received_at": snapshot["received_at"],
                    "exchange_timestamp": snapshot["exchange_timestamp"],
                    "event_type": snapshot["event_type"],
                    "asset_id": snapshot["asset_id"],
                    "num_bid_levels": snapshot["num_bid_levels"],
                    "num_ask_levels": snapshot["num_ask_levels"],
                    "best_bid_price": snapshot["best_bid_price"],
                    "best_bid_size": snapshot["best_bid_size"],
                    "best_ask_price": snapshot["best_ask_price"],
                    "best_ask_size": snapshot["best_ask_size"],
                }

                # Store full orderbook as JSON string (preserves all levels)
                record["bids_json"] = json.dumps(snapshot["bids"])
                record["asks_json"] = json.dumps(snapshot["asks"])

                records.append(record)

            # Create DataFrame
            df = pd.DataFrame(records)

            # Convert timestamps
            df["received_at"] = pd.to_datetime(df["received_at"])
            if df["exchange_timestamp"].notna().any():
                df["exchange_timestamp"] = pd.to_datetime(df["exchange_timestamp"], unit='ms')

            # Generate filename
            asset_short = asset_id[:12]
            filename = self.processed_data_dir / f"orderbook_{asset_short}.parquet"

            # Save to parquet
            df.to_parquet(filename, index=False, engine='pyarrow', compression='snappy')

            print(f"  Saved {len(df):,} snapshots for asset {asset_short}... to {filename.name}")

    def process_all_files(self):
        """
        Process all .jsonl files in the raw data directory.
        """
        # Find all .jsonl files
        jsonl_files = sorted(self.raw_data_dir.glob("*.jsonl"))

        if not jsonl_files:
            print(f"\nNo .jsonl files found in {self.raw_data_dir}")
            return

        print(f"\nFound {len(jsonl_files)} file(s) to process")

        # Process each file
        for filepath in jsonl_files:
            self.process_file(filepath)

        # Save results
        self.save_to_parquet()

        # Print statistics
        self.print_statistics()

    def print_statistics(self):
        """Print processing statistics."""
        print("\n" + "="*80)
        print("PROCESSING COMPLETE - STATISTICS")
        print("="*80)
        print(f"Messages processed: {self.messages_processed:,}")
        print(f"Book events: {self.book_events:,}")
        print(f"Price change events: {self.price_change_events:,}")
        print(f"\nAssets processed: {len(self.snapshots)}")

        for asset_id, snapshots in self.snapshots.items():
            print(f"  {asset_id[:12]}...: {len(snapshots):,} snapshots")

        print("="*80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Process raw Polymarket WebSocket data into orderbook snapshots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process with default directories
  python process_orderbook_data.py

  # Specify custom directories
  python process_orderbook_data.py --raw-dir ./my_raw_data --processed-dir ./my_processed_data
        """
    )

    parser.add_argument(
        '--raw-dir',
        type=str,
        default="./polymarket_raw_data",
        help='Directory containing raw .jsonl files (default: ./polymarket_raw_data)'
    )

    parser.add_argument(
        '--processed-dir',
        type=str,
        default="./polymarket_processed_data",
        help='Directory to save processed parquet files (default: ./polymarket_processed_data)'
    )

    args = parser.parse_args()

    # Create processor
    print("="*80)
    print("POLYMARKET ORDERBOOK DATA PROCESSOR")
    print("="*80)
    print(f"Raw data directory: {args.raw_dir}")
    print(f"Processed data directory: {args.processed_dir}")
    print("="*80)

    processor = OrderbookProcessor(
        raw_data_dir=args.raw_dir,
        processed_data_dir=args.processed_dir
    )

    # Process all files
    processor.process_all_files()

    print("\nProcessing complete!")


if __name__ == "__main__":
    main()
