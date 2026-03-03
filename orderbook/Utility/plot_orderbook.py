"""
Plot orderbook visualization with time on x-axis, price on y-axis, and size as transparency.
Asks are shown in green, bids in red.
"""

import pandas as pd
import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from pathlib import Path
from datetime import datetime


def load_and_prepare_data(filepath):
    """Load parquet file and extract orderbook levels"""
    print(f"Loading data from {filepath}...")
    df = pd.read_parquet(filepath)

    # Convert timestamp to datetime if not already
    if not pd.api.types.is_datetime64_any_dtype(df['received_at']):
        df['received_at'] = pd.to_datetime(df['received_at'])

    print(f"Loaded {len(df)} orderbook snapshots")
    print(f"Time range: {df['received_at'].min()} to {df['received_at'].max()}")

    return df


def extract_orderbook_levels(df):
    """Extract all price levels and sizes from JSON columns"""
    bid_data = []
    ask_data = []

    print("Extracting orderbook levels...")

    for idx, row in df.iterrows():
        timestamp = row['received_at']

        # Parse bids
        if pd.notna(row['bids_json']):
            bids = json.loads(row['bids_json'])
            for price_str, size_str in bids:
                price = float(price_str)
                size = float(size_str)
                if size > 0:  # Only include non-zero sizes
                    bid_data.append({
                        'timestamp': timestamp,
                        'price': price,
                        'size': size
                    })

        # Parse asks
        if pd.notna(row['asks_json']):
            asks = json.loads(row['asks_json'])
            for price_str, size_str in asks:
                price = float(price_str)
                size = float(size_str)
                if size > 0:  # Only include non-zero sizes
                    ask_data.append({
                        'timestamp': timestamp,
                        'price': price,
                        'size': size
                    })

    bid_df = pd.DataFrame(bid_data)
    ask_df = pd.DataFrame(ask_data)

    print(f"Extracted {len(bid_df)} bid levels and {len(ask_df)} ask levels")

    return bid_df, ask_df


def normalize_size_to_alpha(sizes, min_alpha=0.1, max_alpha=0.9):
    """
    Normalize sizes to alpha (transparency) values between min_alpha and max_alpha.
    Larger sizes get higher alpha (more opaque).
    """
    if len(sizes) == 0:
        return np.array([])

    sizes = np.array(sizes)

    # Use log scale for better visualization of size differences
    log_sizes = np.log1p(sizes)  # log(1 + size) to handle zeros

    # Normalize to [0, 1]
    min_log = log_sizes.min()
    max_log = log_sizes.max()

    if max_log == min_log:
        normalized = np.ones_like(log_sizes) * 0.5
    else:
        normalized = (log_sizes - min_log) / (max_log - min_log)

    # Scale to [min_alpha, max_alpha]
    alphas = min_alpha + normalized * (max_alpha - min_alpha)

    return alphas


def plot_orderbook(bid_df, ask_df, title="Orderbook Visualization", figsize=(16, 10)):
    """
    Create orderbook visualization with time on x-axis, price on y-axis,
    and size mapped to transparency.
    """
    print("Creating visualization...")

    fig, ax = plt.subplots(figsize=figsize)

    # Plot bids (red)
    if len(bid_df) > 0:
        bid_alphas = normalize_size_to_alpha(bid_df['size'].values)

        # Create RGBA colors with varying alpha
        bid_colors = np.zeros((len(bid_df), 4))
        bid_colors[:, 0] = 1.0  # Red channel
        bid_colors[:, 3] = bid_alphas  # Alpha channel

        ax.scatter(
            bid_df['timestamp'],
            bid_df['price'],
            c=bid_colors,
            s=20,  # Point size
            marker='s',  # Square markers
            label='Bids',
            edgecolors='none'
        )

    # Plot asks (green)
    if len(ask_df) > 0:
        ask_alphas = normalize_size_to_alpha(ask_df['size'].values)

        # Create RGBA colors with varying alpha
        ask_colors = np.zeros((len(ask_df), 4))
        ask_colors[:, 1] = 1.0  # Green channel
        ask_colors[:, 3] = ask_alphas  # Alpha channel

        ax.scatter(
            ask_df['timestamp'],
            ask_df['price'],
            c=ask_colors,
            s=20,  # Point size
            marker='s',  # Square markers
            label='Asks',
            edgecolors='none'
        )

    # Format x-axis (time)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45, ha='right')

    # Labels and title
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Price', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')

    # Add legend
    ax.legend(loc='upper right', fontsize=10)

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--')

    # Tight layout
    plt.tight_layout()

    print("Visualization created!")

    return fig, ax


def plot_orderbook_from_file(filepath, output_path=None):
    """
    Complete workflow: load data, extract levels, and create visualization.

    Args:
        filepath: Path to processed parquet file
        output_path: Optional path to save the plot (e.g., 'orderbook_plot.png')
    """
    # Load data
    df = load_and_prepare_data(filepath)

    # Get asset ID for title
    asset_id = df['asset_id'].iloc[0] if 'asset_id' in df.columns else 'Unknown'

    # Extract orderbook levels
    bid_df, ask_df = extract_orderbook_levels(df)

    # Create plot
    title = f"Orderbook Visualization - Asset {asset_id}"
    fig, ax = plot_orderbook(bid_df, ask_df, title=title)

    # Save if output path provided
    if output_path:
        print(f"Saving plot to {output_path}...")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {output_path}")

    # Show plot
    plt.show()

    return fig, ax


def plot_all_assets_in_directory(processed_data_dir="./polymarket_processed_data"):
    """
    Plot orderbook visualization for all processed parquet files in directory.
    """
    data_dir = Path(processed_data_dir)

    if not data_dir.exists():
        print(f"Error: Directory {data_dir} does not exist")
        return

    parquet_files = list(data_dir.glob("orderbook_*.parquet"))

    if not parquet_files:
        print(f"No parquet files found in {data_dir}")
        return

    print(f"Found {len(parquet_files)} parquet files")

    for filepath in parquet_files:
        print(f"\n{'='*80}")
        print(f"Processing: {filepath.name}")
        print('='*80)

        # Create output filename
        output_filename = filepath.stem + "_plot.png"
        output_path = data_dir / output_filename

        try:
            plot_orderbook_from_file(str(filepath), output_path=str(output_path))
        except Exception as e:
            print(f"Error processing {filepath.name}: {e}")
            continue


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Plot specific file
        filepath = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else None
        plot_orderbook_from_file(filepath, output_path)
    else:
        # Plot all files in processed data directory
        print("No file specified, plotting all files in ./polymarket_processed_data")
        plot_all_assets_in_directory()
