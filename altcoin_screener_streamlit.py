# altcoin_screener_streamlit.py

import streamlit as st
import requests
import pandas as pd
import time
import os
import math
from datetime import datetime
from rhythmic_analyzer import analyze_with_rhythmic
import re
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Altcoin Screener Login", page_icon="📈", layout="centered")


# --- AUTHENTICATION LOGIC WITH CUSTOM UI ---

def check_password():
    """Returns `True` if the user has entered the correct password."""

    # --- Custom CSS to style the login page ---
    st.markdown("""
    <style>
        /* Center the login form */
        .stApp {
            background-color: #f0f2f6; /* A light gray background */
        }
        .main > div {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        /* Style the login container */
        .st-emotion-cache-r421ms {
            background-color: white;
            padding: 2rem 3rem;
            border-radius: 15px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 450px;
        }
        /* Style the title */
        h1 {
            text-align: center;
            margin-bottom: 0.5rem;
        }
        /* Style the subtitle */
        .st-emotion-cache-1629p8f p {
            text-align: center;
            color: #666;
            margin-bottom: 2rem;
        }
        /* Style the login button */
        .stButton button {
            width: 100%;
            border-radius: 8px;
            background-color: #1a73e8;
            color: white;
            border: none;
        }
    </style>
    """, unsafe_allow_html=True)

    def login():
        """Validates credentials and updates session state."""
        user_credentials = st.secrets["credentials"]
        if (
            st.session_state["login_username"] in user_credentials["usernames"]
            and st.session_state["login_password"] == user_credentials["passwords"][user_credentials["usernames"].index(st.session_state["login_username"])]
        ):
            st.session_state["authenticated"] = True
        else:
            st.session_state["authenticated"] = False
            st.error("نام کاربری یا رمز عبور اشتباه است")

    # --- Main Login UI Logic ---
    if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
        st.title("Welcome Back! 👋")
        st.markdown("<p>برای ادامه وارد حساب کاربری خود شوید</p>", unsafe_allow_html=True)
        
        st.text_input("نام کاربری", key="login_username")
        st.text_input("رمز عبور", type="password", key="login_password")
        
        st.button("ورود", on_click=login)
        st.stop()


# --- MAIN APP LOGIC (The Screener) ---

def main_app():
    """This function contains the entire screener application."""
    
    st.set_page_config(page_title="Altcoin Screener", page_icon="📈", layout="wide")
    st.title("📈 داشبورد غربال‌گری و تحلیل ریتمیک آلت‌کوین‌ها")
    
    API_URL  = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"
    PER_PAGE = 100

    RAW_COLS = {'symbol': 'symbol', 'name': 'name', 'price': 'price', 'volume24h': 'volume24h', 'marketCap': 'marketCap', 'percentChange7d': 'percentChange7d'}
    PROCESSED_COLS = {'symbol': 'symbol', 'name': 'name', 'price': 'price', 'volume_24h': 'volume_24h', 'market_cap': 'market_cap', 'percent_change_7d': 'percent_change_7d'}
    RENAME_MAP = {RAW_COLS['volume24h']: PROCESSED_COLS['volume_24h'], RAW_COLS['marketCap']: PROCESSED_COLS['market_cap'], RAW_COLS['percentChange7d']: PROCESSED_COLS['percent_change_7d']}
    NUMERIC_COLS = [PROCESSED_COLS['price'], PROCESSED_COLS['volume_24h'], PROCESSED_COLS['market_cap'], PROCESSED_COLS['percent_change_7d']]

    PRESETS = {
        "Conservative": {'min_market_cap': 50e6, 'max_market_cap': 500e6, 'min_volume_mc': 0.10, 'max_volume_mc': 0.80, 'min_change_7d': -2.0, 'max_change_7d': 12.0},
        "Balanced": {'min_market_cap': 10e6, 'max_market_cap': 150e6, 'min_volume_mc': 0.20, 'max_volume_mc': 1.00, 'min_change_7d': -2.0, 'max_change_7d': 15.0},
        "Aggressive": {'min_market_cap': 1e6, 'max_market_cap': 100e6, 'min_volume_mc': 0.30, 'max_volume_mc': 2.00, 'min_change_7d': -8.0, 'max_change_7d': 25.0}
    }

    @st.cache_data(ttl=14400)
    def load_or_fetch_data():
        def fetch_total_coins():
            r = requests.get(API_URL, params={'start':1,'limit':1})
            r.raise_for_status()
            return int(r.json()['data']['totalCount'])
        def fetch_page(start=1, limit=PER_PAGE):
            params = {'start': start, 'limit': limit, 'sortBy':'market_cap','sortType':'desc'}
            r = requests.get(API_URL, params=params)
            r.raise_for_status()
            return r.json()['data']['cryptoCurrencyList']
        with st.spinner("در حال واکشی تازه‌ترین داده‌ها از سرور... (این فرآیند ممکن است چند دقیقه طول بکشد و فقط هر ۴ ساعت یکبار انجام می‌شود)"):
            try:
                total_coins_to_fetch = fetch_total_coins()
            except Exception as e:
                st.error(f"خطا در دریافت تعداد کل کوین‌ها: {e}")
                return None
            rows, fetch_limit, start_index = [], min(total_coins_to_fetch, 10000), 1
            while start_index <= fetch_limit:
                try:
                    lst = fetch_page(start=start_index, limit=PER_PAGE)
                    if not lst: break
                    for c in lst:
                        q = c.get('quotes', [{}])[0]
                        rows.append({RAW_COLS['symbol']: c.get('symbol'), RAW_COLS['name']: c.get('name'), RAW_COLS['price']: q.get('price', None), RAW_COLS['volume24h']: q.get('volume24h', None), RAW_COLS['marketCap']: q.get('marketCap', None), RAW_COLS['percentChange7d']: q.get('percentChange7d', None)})
                    start_index += PER_PAGE
                    time.sleep(0.5)
                except Exception as e:
                    st.error(f"خطا در واکشی: {e}")
                    break
        return pd.DataFrame(rows)

    def process_dataframe(df: pd.DataFrame):
        if df is None or df.empty: return None
        processed_df = df.copy()
        processed_df.rename(columns=RENAME_MAP, inplace=True)
        missing_cols = [col for col in NUMERIC_COLS if col not in processed_df.columns]
        if missing_cols:
            st.error(f"داده‌های واکشی شده ستون‌های مورد نیاز را ندارند: `{missing_cols}`.")
            return None
        for col in NUMERIC_COLS:
            processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')
        critical_cols_for_zero_check = [PROCESSED_COLS['market_cap'], PROCESSED_COLS['volume_24h']]
        for col in critical_cols_for_zero_check:
            processed_df[col] = processed_df[col].replace(0, np.nan)
        processed_df.dropna(subset=NUMERIC_COLS, inplace=True)
        return processed_df

    def style_dataframe(df):
        def _color_change(val):
            if not isinstance(val, (int, float)): return ''
            color = '#4CAF50' if val > 0 else ('#F44336' if val < 0 else 'white')
            return f'color: {color}'
        def _style_vci(v):
            if not isinstance(v, (int, float)): return ''
            if v > 2.5: return 'background-color: #FFC107'
            if v > 1.6: return 'background-color: #4CAF50'
            return ''
        styled = df.style.map(_color_change, subset=[col for col in [PROCESSED_COLS['percent_change_7d'], 'mom'] if col in df.columns])
        if 'vci' in df.columns:
            styled = styled.map(_style_vci, subset=['vci'])
        formats = {PROCESSED_COLS['price']: "${:,.4f}", PROCESSED_COLS['market_cap']: "${:,.0f}", PROCESSED_COLS['volume_24h']: "${:,.0f}", PROCESSED_COLS['percent_change_7d']: "{:,.2f}%", "mom": "{:,.2f}%", "volume_mc_ratio": "{:,.2f}", "score": "{:,.3f}"}
        return styled.format({k: v for k, v in formats.items() if k in df.columns})

    def make_name_clickable(df):
        df_display = df.copy()
        if 'name' not in df_display.columns: return df_display
        def _create_slug(name):
            return re.sub(r'[^a-zA-Z0-9 -]', '', str(name)).strip().lower().replace(' ', '-')
        df_display['name'] = df_display.apply(lambda row: f'<a target="_blank" href="https://coinmarketcap.com/currencies/{_create_slug(row["name"])}/">{row["name"]}</a>', axis=1)
        return df_display

    if st.sidebar.button("خروج از حساب"):
        st.session_state["authenticated"] = False
        st.rerun()
        
    st.sidebar.header("تنظیمات فیلتر")
    preset = st.sidebar.selectbox("انتخاب پریست", list(PRESETS.keys()), index=1)
    p = PRESETS[preset]

    with st.sidebar.expander("⚙️ تنظیمات دستی"):
        min_mc = st.number_input("حداقل مارکت کپ ($)", value=p['min_market_cap'], step=1e6, format="%d")
        max_mc = st.number_input("حداکثر مارکت کپ ($)", value=p['max_market_cap'], step=1e6, format="%d")
        min_vmc = st.slider("حداقل نسبت حجم/مارکت کپ", 0.0, 5.0, p['min_volume_mc'], step=0.01)
        max_vmc = st.slider("حداکثر نسبت حجم/مارکت کپ", 0.0, 5.0, p['max_volume_mc'], step=0.01)
        min_ch7 = st.slider("حداقل تغییرات ۷ روزه (%)", -50.0, 50.0, p['min_change_7d'])
        max_ch7 = st.slider("حداکثر تغییرات ۷ روزه (%)", -50.0, 100.0, p['max_change_7d'])

    raw_df = load_or_fetch_data()
    if raw_df is None or raw_df.empty:
        st.error("خطا در واکشی داده‌ها.")
        st.stop()
    df = process_dataframe(raw_df)
    if df is None or df.empty:
        st.warning("هیچ ارز معتبری برای تحلیل یافت نشد.")
        st.stop()
        
    st.sidebar.markdown("---")
    st.sidebar.header("آمار داده‌ها")
    st.sidebar.metric("تعداد کل ارزهای واکشی شده (خام)", f"{len(raw_df):,}")
    st.sidebar.metric("تعداد ارزهای معتبر (پس از پاکسازی)", f"{len(df):,}")

    filter_params = {'min_market_cap': min_mc, 'max_market_cap': max_mc, 'min_volume_mc': min_vmc, 'max_volume_mc': max_vmc, 'min_change_7d': min_ch7, 'max_change_7d': max_ch7}
    df['volume_mc_ratio'] = df[PROCESSED_COLS['volume_24h']] / (df[PROCESSED_COLS['market_cap']] + 1e-9)
    filtered = df[(df[PROCESSED_COLS['market_cap']] >= filter_params['min_market_cap']) & (df[PROCESSED_COLS['market_cap']] <= filter_params['max_market_cap']) & (df['volume_mc_ratio'] >= filter_params['min_volume_mc']) & (df['volume_mc_ratio'] <= filter_params['max_volume_mc']) & (df[PROCESSED_COLS['percent_change_7d']] >= filter_params['min_change_7d']) & (df[PROCESSED_COLS['percent_change_7d']] <= filter_params['max_change_7d'])]

    st.info(f"از مجموع **{len(df):,}** ارز معتبر بررسی شده، **{len(filtered):,}** ارز با فیلترهای شما مطابقت دارند.")

    tab1, tab2 = st.tabs(["📄 **نتایج اولیه**", "🎯 **تحلیل ریتمیک**"])
    with tab1:
        st.subheader("لیست کاندیداهای اولیه")
        if filtered.empty: st.warning("هیچ ارزی با فیلترهای فعلی یافت نشد.")
        else: st.write(style_dataframe(make_name_clickable(filtered)).to_html(escape=False), unsafe_allow_html=True)

    with tab2:
        st.subheader("تحلیل عمیق بر اساس ریتم بازار")
        if filtered.empty: st.warning("برای تحلیل ریتمیک، ابتدا باید کاندیداهایی در تب نتایج اولیه وجود داشته باشد.")
        elif st.button("🚀 شروع تحلیل ریتمیک نهایی"):
            with st.spinner("لطفا صبر کنید، تحلیل در حال انجام است..."):
                recs = filtered[[PROCESSED_COLS['symbol'], PROCESSED_COLS['name'], PROCESSED_COLS['percent_change_7d']]].to_dict("records")
                progress_bar = st.progress(0.0, text="آماده‌سازی برای تحلیل...")
                status_text = st.empty()
                results = analyze_with_rhythmic(recs, progress_bar=progress_bar, status_text=status_text)
            if results:
                st.success("✅ تحلیل با موفقیت به پایان رسید!")
                df_r = pd.DataFrame(results)
                df_r = pd.merge(df_r, filtered[[PROCESSED_COLS['symbol'], PROCESSED_COLS['name']]], on=PROCESSED_COLS['symbol'], how='left')
                passed = df_r[df_r["pass"] == True].sort_values("score", ascending=False)
                st.markdown("---"); st.subheader("📊 خلاصه نتایج")
                col1, col2, col3 = st.columns(3)
                col1.metric("تعداد کاندیداها", f"{len(df_r):,}"); col2.metric("✅ قبول‌شدگان", f"{len(passed):,}"); col3.metric("❌ ردشدگان", f"{len(df_r) - len(passed):,}")
                st.markdown("---"); st.subheader("🏆 لیست نهایی قبول‌شدگان")
                if passed.empty: st.warning("هیچ ارزی از تحلیل ریتمیک عبور نکرد.")
                else: st.write(style_dataframe(make_name_clickable(passed)).to_html(escape=False), unsafe_allow_html=True)
            else:
                st.error("تحلیل نتیجه‌ای در بر نداشت یا با خطا مواجه شد.")

# --- SCRIPT EXECUTION STARTS HERE ---

# Initialize session state if not already done
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Check password and display login if not authenticated
check_password()

# If authenticated, run the main app
main_app()
