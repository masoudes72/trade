# altcoin_screener_streamlit.py

import streamlit as st
import requests
import pandas as pd
import time
import os
import math
from datetime import datetime
from rhythmic_analyzer import analyze_with_rhythmic, get_ohlcv_from_coinbase
import re
import numpy as np

# --- PAGE CONFIG (Set once at the top) ---
st.set_page_config(page_title="Crypto Screener", page_icon="📈", layout="wide")

# --- AUTHENTICATION & LOGIN PAGE UI ---
def render_login_page():
    # ... (This function is complete and correct, no changes needed)
    def login():
        try:
            user_credentials = st.secrets["credentials"]
            if (st.session_state["username"] in user_credentials["usernames"] and st.session_state["password"] == user_credentials["passwords"][user_credentials["usernames"].index(st.session_state["username"])]):
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.session_state["authenticated"] = False
                st.error("نام کاربری یا رمز عبور اشتباه است")
        except Exception as e:
            st.error(f"خطا در بررسی اطلاعات ورود: {e}")
            st.session_state["authenticated"] = False
    
    st.markdown("""<style>...</style>""", unsafe_allow_html=True) # CSS kept short for brevity
    st.image("logo.png", width=100)
    st.markdown("<h2>CRYPTO FILTER</h2>", unsafe_allow_html=True)
    st.text_input("Username", placeholder="Email Address", key="username", label_visibility="collapsed")
    st.text_input("Password", placeholder="Password", type="password", key="password", label_visibility="collapsed")
    st.button("Log In", on_click=login)
    st.markdown("""<div class="login-footer">...</div>""", unsafe_allow_html=True)

# --- MAIN APP LOGIC ---
def main_app():
    st.markdown("""<style>...</style>""", unsafe_allow_html=True) # Main app CSS is correct
    
    st.title("📈 داشبورد غربال‌گری و تحلیل ریتمیک آلت‌کوین‌ها")
    
    API_URL, PER_PAGE = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing", 100
    RAW_COLS = {'symbol': 'symbol', 'name': 'name', 'price': 'price', 'volume24h': 'volume24h', 'marketCap': 'marketCap', 'percentChange7d': 'percentChange7d'}
    PROCESSED_COLS = {'symbol': 'symbol', 'name': 'name', 'price': 'price', 'volume_24h': 'volume_24h', 'market_cap': 'market_cap', 'percent_change_7d': 'percent_change_7d'}
    RENAME_MAP = {RAW_COLS['volume24h']: PROCESSED_COLS['volume_24h'], RAW_COLS['marketCap']: PROCESSED_COLS['market_cap'], RAW_COLS['percentChange7d']: PROCESSED_COLS['percent_change_7d']}
    NUMERIC_COLS = [PROCESSED_COLS['price'], PROCESSED_COLS['volume_24h'], PROCESSED_COLS['market_cap'], PROCESSED_COLS['percent_change_7d']]
    
    PRESETS = {
        "Conservative": {'min_market_cap': 50e6, 'max_market_cap': 500e6, 'min_volume_mc': 0.10, 'max_volume_mc': 0.80, 'min_change_7d': -2.0, 'max_change_7d': 12.0},
        "Balanced": {'min_market_cap': 10e6, 'max_market_cap': 150e6, 'min_volume_mc': 0.20, 'max_volume_mc': 1.00, 'min_change_7d': -2.0, 'max_change_7d': 15.0},
        "Aggressive": {'min_market_cap': 1e6, 'max_market_cap': 100e6, 'min_volume_mc': 0.30, 'max_volume_mc': 2.00, 'min_change_7d': -8.0, 'max_change_7d': 25.0}
    }

    # --- NEW DATA FETCHING LOGIC WITH PROGRESS BAR ---

    @st.cache_data(ttl=14400)
    def fetch_page_cached(start_index):
        """Caches the result of fetching a single page."""
        params = {'start': start_index, 'limit': PER_PAGE, 'sortBy':'market_cap','sortType':'desc'}
        r = requests.get(API_URL, params=params)
        r.raise_for_status()
        return r.json()['data']['cryptoCurrencyList']

    def fetch_all_data_with_progress():
        """Orchestrates the fetch, updates the progress bar, and returns a DataFrame."""
        try:
            total_coins_to_fetch = min(fetch_total_coins(), 10000)
        except Exception as e:
            st.sidebar.error(f"خطا در دریافت تعداد کل کوین‌ها: {e}")
            return None

        bar = st.sidebar.progress(0, text="شروع واکشی...")
        rows = []
        
        for start_index in range(1, total_coins_to_fetch, PER_PAGE):
            try:
                lst = fetch_page_cached(start_index)
                if not lst:
                    break
                
                for c in lst:
                    q = c.get('quotes', [{}])[0]
                    rows.append({'symbol': c.get('symbol'), 'name': c.get('name'), 'price': q.get('price', None), 'volume24h': q.get('volume24h', None), 'marketCap': q.get('marketCap', None), 'percentChange7d': q.get('percentChange7d', None)})
                
                progress = min(len(rows) / total_coins_to_fetch, 1.0)
                bar.progress(progress, text=f"واکشی {len(rows)}/{total_coins_to_fetch} ارز...")
                time.sleep(0.1) # A small sleep to make UI updates smooth
            except Exception as e:
                st.sidebar.error(f"خطا در واکشی صفحه: {e}")
                break
        
        bar.progress(1.0, "واکشی کامل شد!")
        return pd.DataFrame(rows)

    def fetch_total_coins():
        r = requests.get(API_URL, params={'start':1,'limit':1}); r.raise_for_status(); return int(r.json()['data']['totalCount'])

    # --- (Other helper functions like process_dataframe, etc. remain unchanged) ---
    def process_dataframe(df: pd.DataFrame):
        if df is None or df.empty: return None
        processed_df = df.copy()
        processed_df.rename(columns=RENAME_MAP, inplace=True)
        for col in NUMERIC_COLS: processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')
        critical_cols = [PROCESSED_COLS['market_cap'], PROCESSED_COLS['volume_24h']]
        for col in critical_cols: processed_df[col] = processed_df[col].replace(0, np.nan)
        processed_df.dropna(subset=NUMERIC_COLS, inplace=True)
        return processed_df
    def style_dataframe(df):
        def _color_change(val):
            if not isinstance(val, (int, float)): return ''; return f"color: {'#4CAF50' if val > 0 else ('#F44336' if val < 0 else 'white')}"
        def _style_vci(v):
            if not isinstance(v, (int, float)): return '';
            if v > 2.5: return 'background-color: #FFC107';
            if v > 1.6: return 'background-color: #4CAF50'; return ''
        styled = df.style.map(_color_change, subset=[c for c in [PROCESSED_COLS['percent_change_7d'], 'mom'] if c in df.columns])
        if 'vci' in df.columns: styled = styled.map(_style_vci, subset=['vci'])
        formats = {'price': "${:,.4f}",'market_cap': "${:,.0f}",'volume_24h': "${:,.0f}",'percent_change_7d': "{:,.2f}%","mom": "{:,.2f}%", "volume_mc_ratio": "{:,.2f}", "score": "{:,.3f}"}
        return styled.format({k: v for k, v in formats.items() if k in df.columns})
    def make_name_clickable(df):
        df_display = df.copy()
        if 'name' not in df_display.columns: return df_display
        def _create_slug(name): return re.sub(r'[^a-zA-Z0-9 -]', '', str(name)).strip().lower().replace(' ', '-')
        df_display['name'] = df_display.apply(lambda row: f'<a target="_blank" href="https://coinmarketcap.com/currencies/{_create_slug(row["name"])}/">{row["name"]}</a>', axis=1)
        return df_display

    # --- SIDEBAR CONTROLS ---
    if st.sidebar.button("خروج از حساب"):
        st.session_state["authenticated"] = False; st.rerun()
    
    st.sidebar.header("واکشی اطلاعات")
    if "raw_df" not in st.session_state:
        st.session_state.raw_df = None
    
    if st.sidebar.button("🔄 واکشی داده‌های جدید", type="primary"):
        with st.spinner("لطفا صبر کنید..."):
            st.cache_data.clear() # Clear all caches
            st.session_state.raw_df = fetch_all_data_with_progress()
            st.rerun()

    st.sidebar.header("تنظیمات فیلتر")
    # ... (Filter controls are unchanged)
    preset = st.sidebar.selectbox("انتخاب پریست", list(PRESETS.keys()), index=1); p = PRESETS[preset]
    with st.sidebar.expander("⚙️ تنظیمات دستی"):
        min_mc = st.number_input("...", value=p['min_market_cap'],...); max_mc = st.number_input("...", value=p['max_market_cap'],...)
        min_vmc = st.slider("...", 0.0, 5.0, p['min_volume_mc'],...); max_vmc = st.slider("...", 0.0, 5.0, p['max_volume_mc'],...)
        min_ch7 = st.slider("...", -50.0, 50.0, p['min_change_7d']); max_ch7 = st.slider("...", -50.0, 100.0, p['max_change_7d'])

    # --- DATA LOADING AND PROCESSING ---
    if st.session_state.raw_df is None:
        st.info("📊 برای شروع، لطفاً روی دکمه «واکشی داده‌های جدید» در سایدبار کلیک کنید.")
        st.stop()
    
    raw_df = st.session_state.raw_df
    df = process_dataframe(raw_df)
    if df is None or df.empty: st.warning("هیچ ارز معتبری برای تحلیل یافت نشد."); st.stop()
        
    st.sidebar.markdown("---"); st.sidebar.header("آمار داده‌ها")
    st.sidebar.metric("تعداد کل ارزهای واکشی شده (خام)", f"{len(raw_df):,}")
    st.sidebar.metric("تعداد ارزهای معتبر (پس از پاکسازی)", f"{len(df):,}")

    # ... (The rest of the app, filtering, tabs, rhythmic analysis, etc., is unchanged)
    filter_params = {'min_market_cap': min_mc, ...}; df['volume_mc_ratio'] = df[...] / (df[...] + 1e-9)
    filtered = df[(df[...] >= filter_params[...]) & ...]
    st.info(f"از مجموع **{len(df):,}** ارز معتبر بررسی شده، **{len(filtered):,}** ارز با فیلترهای شما مطابقت دارند.")
    tab1, tab2 = st.tabs(["📄 **نتایج اولیه**", "🎯 **تحلیل ریتمیک**"])
    with tab1:
        st.subheader("لیست کاندیداهای اولیه")
        if filtered.empty: st.warning("هیچ ارزی با فیلترهای فعلی یافت نشد.")
        else: st.write(style_dataframe(make_name_clickable(filtered)).to_html(escape=False), unsafe_allow_html=True)
    with tab2:
        st.subheader("تحلیل عمیق بر اساس ریتم بازار")
        if filtered.empty: st.warning("...")
        elif st.button("🚀 شروع تحلیل ریتمیک نهایی"):
            recs = filtered[[...]].to_dict("records")
            progress_bar = st.progress(0.0, text="آماده‌سازی برای تحلیل...")
            status_text = st.empty()
            results = analyze_with_rhythmic(recs, progress_bar=progress_bar, status_text=status_text)
            if results:
                st.success("✅ تحلیل با موفقیت به پایان رسید!")
                df_r = pd.DataFrame(results); passed = df_r[df_r["pass"] == True].sort_values("score", ascending=False)
                st.markdown("---"); st.subheader("📊 خلاصه نتایج")
                col1, col2, col3 = st.columns(3); col1.metric("...", f"{len(df_r):,}"); col2.metric("...", f"{len(passed):,}"); col3.metric("...", f"{len(df_r) - len(passed):,}")
                st.markdown("---"); st.subheader("🏆 لیست نهایی قبول‌شدگان")
                if passed.empty: st.warning("هیچ ارزی از تحلیل ریتمیک عبور نکرد.")
                else: st.write(style_dataframe(make_name_clickable(passed)).to_html(escape=False), unsafe_allow_html=True)
            else: st.error("تحلیل نتیجه‌ای در بر نداشت یا با خطا مواجه شد.")

# --- SCRIPT EXECUTION STARTS HERE ---
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False

if st.session_state.get("authenticated", False):
    main_app()
else:
    render_login_page()
