# Kalshi Authentication Setup

## What You Need

Kalshi uses **RSA private key authentication**. You need two files placed at the repo root:

| File | Description | Where to get it |
|------|-------------|-----------------|
| `kalshi_api.txt` | Your API Key ID (short string, e.g. `abc123def456`) | Kalshi website → Settings → API Keys |
| `kalshi_private_key.pem` | Your RSA private key file | Downloaded when you created the API key |

Both files are gitignored and will never be committed.

## How It Works

1. The script signs a timestamp using your private key (RSA-PSS signature)
2. The signature + Key ID are sent as headers on the WebSocket connection
3. Kalshi verifies the signature using the public key on their end

The private key never leaves your machine.

## Setup Steps

### Step 1: Get Your Credentials from Kalshi

1. Go to https://kalshi.com and log in
2. Navigate to **Settings → API Keys**
3. Copy your **API Key ID** (the short string shown on the page)
4. Locate your **private key `.pem` file** — this was downloaded when you first created the key

The `.pem` file looks like:
```
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...
(many lines)
-----END PRIVATE KEY-----
```

If you lost it, delete the old key on Kalshi and create a new one — you only get one chance to download it.

### Step 2: Place Your Files

Put both files at the repo root:

```
kalshi-polymarket-arb/
├── kalshi_api.txt            ← paste your Key ID here (just the string, one line)
├── kalshi_private_key.pem    ← your private key file
├── realtime/
├── orderbook/
└── ...
```

### Step 3: Test Your Setup

Run the standalone orderbook viewer:

```bash
uv run python realtime/kalshi_realtime_orderbook.py
```

You should see:
```
Connected to Kalshi WebSocket
Subscribed to: <ticker>
Receiving and processing orderbook updates (Ctrl+C to stop)...
```

If authentication fails you'll get a `403` or connection error — double-check that the Key ID in `kalshi_api.txt` matches the key whose `.pem` file you're using.

## Common Issues

### "The private key doesn't work"
- Make sure the `.pem` file includes the full `-----BEGIN PRIVATE KEY-----` / `-----END PRIVATE KEY-----` markers
- Make sure there are no extra lines of text in the file
- Make sure the Key ID in `kalshi_api.txt` corresponds to this specific key (not a different one)

### "I lost my private key"
1. Go to Kalshi Settings → API Keys
2. Delete the old key
3. Create a new key and download the `.pem` immediately
