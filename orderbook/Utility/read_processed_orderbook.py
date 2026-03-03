"""
Helper script to read and analyze processed orderbook data.

Shows how to:
- Load parquet files
- Extract orderbook snapshots
- Display full orderbook at specific times
- Analyze orderbook statistics
"""
import pandas as pd
import json
from pathlib import Path


def load_orderbook_data(filepath):
    """
    Load processed orderbook data from parquet file.

    Args:
        filepath: Path to the parquet file

    Returns:
        DataFrame with orderbook snapshots
    """
    df = pd.read_parquet(filepath)
    print(f"Loaded {len(df):,} snapshots from {Path(filepath).name}")
    return df


def display_orderbook_snapshot(df, index):
    """
    Display a single orderbook snapshot.

    Args:
        df: DataFrame with orderbook data
        index: Row index to display
    """
    row = df.iloc[index]

    print("\n" + "="*80)
    print(f"ORDERBOOK SNAPSHOT #{index}")
    print("="*80)
    print(f"Received at: {row['received_at']}")
    print(f"Exchange timestamp: {row['exchange_timestamp']}")
    print(f"Event type: {row['event_type']}")
    print(f"Asset ID: {row['asset_id'][:20]}...")
    print(f"\nBest bid: {row['best_bid_price']} @ {row['best_bid_size']}")
    print(f"Best ask: {row['best_ask_price']} @ {row['best_ask_size']}")
    print(f"\nTotal levels: {row['num_bid_levels']} bids, {row['num_ask_levels']} asks")

    # Parse and display full orderbook
    bids = json.loads(row['bids_json'])
    asks = json.loads(row['asks_json'])

    print(f"\n{'BIDS (Top 10)':<40} | {'ASKS (Top 10)':<40}")
    print(f"{'-'*40} | {'-'*40}")

    max_rows = min(10, max(len(bids), len(asks)))

    for i in range(max_rows):
        # Bid side
        if i < len(bids):
            bid_price, bid_size = bids[i]
            bid_str = f"{bid_price:>10} @ {bid_size:<15}"
        else:
            bid_str = " " * 40

        # Ask side
        if i < len(asks):
            ask_price, ask_size = asks[i]
            ask_str = f"{ask_price:>10} @ {ask_size:<15}"
        else:
            ask_str = " " * 40

        print(f"{bid_str} | {ask_str}")

    print("="*80)


def analyze_orderbook_stats(df):
    """
    Print statistics about the orderbook data.

    Args:
        df: DataFrame with orderbook data
    """
    print("\n" + "="*80)
    print("ORDERBOOK STATISTICS")
    print("="*80)

    print(f"\nTotal snapshots: {len(df):,}")
    print(f"Time range: {df['received_at'].min()} to {df['received_at'].max()}")
    duration = (df['received_at'].max() - df['received_at'].min()).total_seconds()
    print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")

    print(f"\nEvent type breakdown:")
    print(df['event_type'].value_counts())

    print(f"\nOrderbook depth:")
    print(f"  Avg bid levels: {df['num_bid_levels'].mean():.1f}")
    print(f"  Avg ask levels: {df['num_ask_levels'].mean():.1f}")
    print(f"  Max bid levels: {df['num_bid_levels'].max()}")
    print(f"  Max ask levels: {df['num_ask_levels'].max()}")

    print(f"\nBest bid/ask statistics:")
    print(f"  Best bid price range: {df['best_bid_price'].min():.4f} - {df['best_bid_price'].max():.4f}")
    print(f"  Best ask price range: {df['best_ask_price'].min():.4f} - {df['best_ask_price'].max():.4f}")

    # Calculate spread
    df['spread'] = df['best_ask_price'] - df['best_bid_price']
    print(f"\nSpread statistics:")
    print(f"  Mean spread: {df['spread'].mean():.4f}")
    print(f"  Min spread: {df['spread'].min():.4f}")
    print(f"  Max spread: {df['spread'].max():.4f}")

    print("="*80)


def main():
    """Example usage."""
    # Find processed parquet files
    processed_dir = Path("./polymarket_processed_data")

    if not processed_dir.exists():
        print(f"Processed data directory not found: {processed_dir}")
        print("Run process_orderbook_data.py first to create processed data.")
        return

    parquet_files = list(processed_dir.glob("*.parquet"))

    if not parquet_files:
        print(f"No parquet files found in {processed_dir}")
        return

    print("="*80)
    print("PROCESSED ORDERBOOK DATA READER")
    print("="*80)
    print(f"\nFound {len(parquet_files)} parquet file(s):")
    for i, filepath in enumerate(parquet_files, 1):
        print(f"  {i}. {filepath.name}")

    # Load first file as example
    print("\n" + "="*80)
    print("LOADING FIRST FILE AS EXAMPLE")
    print("="*80)

    df = load_orderbook_data(parquet_files[0])

    # Show statistics
    analyze_orderbook_stats(df)

    # Display first snapshot
    print("\nDISPLAYING FIRST SNAPSHOT:")
    display_orderbook_snapshot(df, 0)

    # Display last snapshot
    print("\nDISPLAYING LAST SNAPSHOT:")
    display_orderbook_snapshot(df, len(df) - 1)

    # Display middle snapshot
    middle_idx = len(df) // 2
    print(f"\nDISPLAYING MIDDLE SNAPSHOT (#{middle_idx}):")
    display_orderbook_snapshot(df, middle_idx)


if __name__ == "__main__":
    main()
