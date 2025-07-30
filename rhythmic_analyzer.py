# rhythmic_analyzer.py

import requests
import pandas as pd
import numpy as np
import streamlit as st

# === API endpoints ===
BINANCE_SYMBOLS_URL = "https://api.binance.com/api/v3/exchangeInfo"
BINANCE_OHLCV_URL = "https://api.binance.com/api/v3/klines"
COINGECKO_LIST_URL = "https://api.coingecko.com/api/v3/coins/list"
COINGECKO_OHLC_URL = "https://api.coingecko.com/api/v3/coins/{id}/ohlc"
COINGECKO_VOL_URL = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"
COINPAPRIKA_LIST_URL = "https://api.coinpaprika.com/v1/coins"
COINPAPRIKA_MARKET_URL = "https://api.coinpaprika.com/v1/tickers/{id}/historical"

# === Mapping symbols to ids (Functions) ===
def get_binance_symbols():
    r = requests.get(BINANCE_SYMBOLS_URL)
    r.raise_for_status()
    return {s["symbol"] for s in r.json()["symbols"]}

def get_coingecko_ids():
    r = requests.get(COINGECKO_LIST_URL)
    r.raise_for_status()
    return {item["symbol"].lower(): item["id"] for item in r.json()}

def get_coinpaprika_ids():
    r = requests.get(COINPAPRIKA_LIST_URL)
    r.raise_for_status()
    return {item["symbol"].upper(): item["id"] for item in r.json() if not item.get("is_active") == False}

# --- Robust Initial Loading of Symbol Maps ---
try:
    binance_symbols = get_binance_symbols()
except Exception as e:
    print(f"Warning: Could not fetch Binance symbols. Reason: {e}")
    binance_symbols = set()

try:
    coingecko_map = get_coingecko_ids()
except Exception as e:
    print(f"Warning: Could not fetch CoinGecko IDs. Reason: {e}")
    coingecko_map = {}

try:
    coinpaprika_map = get_coinpaprika_ids()
except Exception as e:
    print(f"Warning: Could not fetch CoinPaprika IDs. Reason: {e}")
    coinpaprika_map = {}

# === Check availability ===
def exists_on_binance(symbol: str) -> bool:
    return (symbol.upper() + "USDT") in binance_symbols

def exists_on_coingecko(symbol: str) -> bool:
    return symbol.lower() in coingecko_map

def exists_on_coinpaprika(symbol: str) -> bool:
    return symbol.upper() in coinpaprika_map

# === Fetch OHLCV from Data Sources ===
def get_ohlcv_from_binance(symbol_usdt: str, interval="1d", limit=30):
    params = {"symbol": symbol_usdt, "interval": interval, "limit": limit}
    r = requests.get(BINANCE_OHLCV_URL, params=params)
    r.raise_for_status()
    df = pd.DataFrame(r.json(), columns=["open_time","open","high","low","close","volume","close_time","quote_asset_volume","num_trades","taker_buy_base_volume","taker_buy_quote_volume","ignore"])
    return {"closes": df["close"].astype(float).tolist(), "volumes": df["volume"].astype(float).tolist()}

def get_ohlcv_from_coingecko(symbol: str, days=30):
    coin_id = coingecko_map.get(symbol.lower())
    if not coin_id: return None
    try:
        r1 = requests.get(COINGECKO_OHLC_URL.format(id=coin_id), params={"vs_currency": "usd", "days": days})
        r2 = requests.get(COINGECKO_VOL_URL.format(id=coin_id), params={"vs_currency": "usd", "days": days, "interval": "daily"})
        if r1.status_code != 200: return None
        closes_df = pd.DataFrame(r1.json(), columns=["time","open","high","low","close"])
        if closes_df.empty: return None
        closes = closes_df["close"].astype(float)
        volumes = [0.0]*len(closes)
        if r2.status_code == 200 and "total_volumes" in r2.json():
            vols_df = pd.DataFrame(r2.json()["total_volumes"], columns=["time","volume"])
            if not vols_df.empty:
                vols = vols_df["volume"].astype(float)
                m = min(len(closes), len(vols))
                return {"closes": closes.tolist()[-m:], "volumes": vols.tolist()[-m:]}
        return {"closes": closes.tolist(), "volumes": volumes}
    except:
        return None

def get_ohlcv_from_coinpaprika(symbol: str, days=30):
    coin_id = coinpaprika_map.get(symbol.upper())
    if not coin_id: return None
    try:
        now = pd.Timestamp.now()
        start = (now - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")
        params = {"start": start, "end": end, "limit": days, "quote": "usd"}
        r = requests.get(COINPAPRIKA_MARKET_URL.format(id=coin_id), params=params)
        if r.status_code != 200: return None
        df = pd.DataFrame(r.json())
        return {"closes": df["close"].astype(float).tolist()[-days:], "volumes": df["volume"].astype(float).tolist()[-days:]}
    except:
        return None

# === Unified fetcher with fallback ===
@st.cache_data(ttl=3600)
def get_ohlcv(symbol: str):
    if exists_on_binance(symbol):
        return get_ohlcv_from_binance(symbol.upper() + "USDT")
    g = get_ohlcv_from_coingecko(symbol)
    if g and sum(g["volumes"]) > 0:
        return g
    if exists_on_coinpaprika(symbol):
        return get_ohlcv_from_coinpaprika(symbol)
    return g or None

# === Rhythm-based filter logic ===
def simple_rhythm_filter(ohlcv: dict, percent_change_7d: float) -> dict:
    closes = np.array(ohlcv["closes"], dtype=float)
    volumes = np.array(ohlcv["volumes"], dtype=float)
    if len(closes) < 30:
        return {"pass": False, "score": 0.0, "reason": "too_few_candles"}
    has_volume = np.nansum(volumes) > 0
    if has_volume:
        v_ref = np.median(volumes[-30:]) + 1e-9
        vci = volumes[-1] / v_ref
        vci_score = np.clip((vci - 1.0) / (2.5 - 1.0), 0, 1)
        vci_for_out = round(vci, 2)
        vci_pass = vci >= 1.6
    else:
        vci_score = 0.0; vci_for_out = None; vci_pass = True
    mom_score = np.clip((percent_change_7d - 0.5) / (12.0 - 0.5), 0, 1)
    score = 0.6 * vci_score + 0.4 * mom_score
    passed = vci_pass and (0.5 <= percent_change_7d <= 12.0)
    return {"pass": passed, "score": round(score, 3), "vci": vci_for_out, "mom": round(percent_change_7d, 2)}

# === Batch analyzer function ===
def analyze_with_rhythmic(coins: list[dict], progress_bar=None, status_text=None) -> list[dict]:
    results = []
    total_coins = len(coins)
    for i, coin in enumerate(coins):
        symbol = coin.get("symbol")
        if status_text: status_text.text(f"در حال تحلیل {symbol}... ({i + 1}/{total_coins})")
        if progress_bar: progress_bar.progress((i + 1) / total_coins)
        try:
            ohlcv = get_ohlcv(symbol)
            if not ohlcv:
                results.append({"symbol": symbol, "pass": False, "score": 0.0, "reason": "no_data"})
                continue
            analysis = simple_rhythm_filter(ohlcv, coin.get("percent_change_7d", 0))
            results.append({"symbol": symbol, **analysis})
        except Exception as e:
            results.append({"symbol": symbol, "pass": False, "score": 0.0, "reason": str(e)})
    if status_text: status_text.text("✅ تحلیل کامل شد!")
    if progress_bar: progress_bar.progress(1.0)
    return results
