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

st.set_page_config(page_title="Altcoin Screener", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

API_URL  = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"
DATA_DIR = "data"
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

def fetch_total_coins():
    r = requests.get(API_URL, params={'start':1,'limit':1})
    r.raise_for_status()
    return int(r.json()['data']['totalCount'])

def fetch_page(start=1, limit=PER_PAGE):
    params = {'start': start, 'limit': limit, 'sortBy':'market_cap','sortType':'desc'}
    r = requests.get(API_URL, params=params)
    r.raise_for_status()
    return r.json()['data']['cryptoCurrencyList']

def save_dataframe(df):
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    df.to_csv(os.path.join(DATA_DIR, f"{today}.csv"), index=False)

@st.cache_data
def load_dataframe():
    today = datetime.now().strftime("%Y-%m-%d")
    path  = os.path.join(DATA_DIR, f"{today}.csv")
    return pd.read_csv(path) if os.path.exists(path) else None

def process_dataframe(df: pd.DataFrame) -> pd.DataFrame | None:
    if df is None: return None
    processed_df = df.copy()
    cols_to_rename = {k: v for k, v in RENAME_MAP.items() if k in processed_df.columns}
    processed_df.rename(columns=cols_to_rename, inplace=True)
    missing_cols = [col for col in NUMERIC_COLS if col not in processed_df.columns]
    if missing_cols:
        st.error(f"فایل داده ناقص است: `{missing_cols}`.")
        return None
    for col in NUMERIC_COLS:
        processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')
    critical_cols_for_zero_check = [PROCESSED_COLS['market_cap'], PROCESSED_COLS['volume_24h']]
    for col in critical_cols_for_zero_check:
        if col in processed_df.columns:
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

st.title("📈 داشبورد غربال‌گری و تحلیل ریتمیک آلت‌کوین‌ها")

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

st.sidebar.markdown("---")

if st.sidebar.button("🔄 واکشی داده‌های جدید", type="primary"):
    with st.spinner("در حال محاسبه تعداد کل ارزها..."):
        try:
            total_coins_to_fetch = fetch_total_coins()
        except Exception as e:
            st.error(f"خطا در دریافت تعداد کل کوین‌ها: {e}")
            st.stop()
    
    rows, fetched_count = [], 0
    bar = st.sidebar.progress(0.0, "شروع واکشی...")
    start_index = 1

    while fetched_count < total_coins_to_fetch:
        try:
            lst = fetch_page(start=start_index, limit=PER_PAGE)
            if not lst: break
            for c in lst:
                q = c.get('quotes', [{}])[0]
                rows.append({
                    RAW_COLS['symbol']: c.get('symbol'), RAW_COLS['name']: c.get('name'),
                    RAW_COLS['price']: q.get('price', None), RAW_COLS['volume24h']: q.get('volume24h', None),
                    RAW_COLS['marketCap']: q.get('marketCap', None), RAW_COLS['percentChange7d']: q.get('percentChange7d', None)
                })
            fetched_count += len(lst)
            if start_index > total_coins_to_fetch : break
            start_index += PER_PAGE
            bar.progress(min(fetched_count / total_coins_to_fetch, 1.0), f"واکشی {fetched_count}/{total_coins_to_fetch} ارز...")
            time.sleep(0.5)
        except Exception as e:
            st.error(f"خطا در واکشی: {e}")
            break
            
    bar.progress(1.0, "واکشی کامل شد!")
            
    if rows:
        save_dataframe(pd.DataFrame(rows))
        st.sidebar.success("داده‌ها ذخیره شد! صفحه در حال بارگذاری مجدد است.")
        time.sleep(2)
        st.rerun()

raw_df = load_dataframe()
if raw_df is None:
    st.info("📊 داده‌ای برای نمایش وجود ندارد. لطفاً با استفاده از دکمه در سایدبار، داده‌های جدید را واکشی کنید.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.header("آمار پردازش داده")
st.sidebar.metric("تعداد کل ارزهای واکشی شده (خام)", f"{len(raw_df):,}")

df = process_dataframe(raw_df)
if df is None:
    st.stop()

st.sidebar.metric("تعداد ارزهای معتبر (پس از پاکسازی)", f"{len(df):,}")

filter_params = {'min_market_cap': min_mc, 'max_market_cap': max_mc, 'min_volume_mc': min_vmc, 'max_volume_mc': max_vmc, 'min_change_7d': min_ch7, 'max_change_7d': max_ch7}
df['volume_mc_ratio'] = df[PROCESSED_COLS['volume_24h']] / (df[PROCESSED_COLS['market_cap']] + 1e-9)
filtered = df[(df[PROCESSED_COLS['market_cap']] >= filter_params['min_market_cap']) & (df[PROCESSED_COLS['market_cap']] <= filter_params['max_market_cap']) & (df['volume_mc_ratio'] >= filter_params['min_volume_mc']) & (df['volume_mc_ratio'] <= filter_params['max_volume_mc']) & (df[PROCESSED_COLS['percent_change_7d']] >= filter_params['min_change_7d']) & (df[PROCESSED_COLS['percent_change_7d']] <= filter_params['max_change_7d'])]

st.info(f"از مجموع **{len(df):,}** ارز معتبر بررسی شده، **{len(filtered):,}** ارز با فیلترهای شما مطابقت دارند.")

tab1, tab2 = st.tabs(["📄 **نتایج اولیه**", "🎯 **تحلیل ریتمیک**"])

with tab1:
    st.subheader("لیست کاندیداهای اولیه")
    if filtered.empty:
        st.warning("هیچ ارزی با فیلترهای فعلی یافت نشد.")
    else:
        display_df = make_name_clickable(filtered)
        styled_df = style_dataframe(display_df)
        st.write(styled_df.to_html(escape=False), unsafe_allow_html=True)

with tab2:
    st.subheader("تحلیل عمیق بر اساس ریتم بازار")
    if filtered.empty:
        st.warning("برای تحلیل ریتمیک، ابتدا باید کاندیداهایی در تب نتایج اولیه وجود داشته باشد.")
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
            
            st.markdown("---")
            st.subheader("📊 خلاصه نتایج")
            col1, col2, col3 = st.columns(3)
            col1.metric("تعداد کاندیداها", f"{len(df_r):,}")
            col2.metric("✅ قبول‌شدگان", f"{len(passed):,}")
            col3.metric("❌ ردشدگان", f"{len(df_r) - len(passed):,}")
            
            st.markdown("---")
            st.subheader("🏆 لیست نهایی قبول‌شدگان")
            if passed.empty:
                st.warning("هیچ ارزی از تحلیل ریتمیک عبور نکرد.")
            else:
                passed_display = make_name_clickable(passed)
                styled_passed = style_dataframe(passed_display)
                st.write(styled_passed.to_html(escape=False), unsafe_allow_html=True)
        else:
            st.error("تحلیل نتیجه‌ای در بر نداشت یا با خطا مواجه شد.")