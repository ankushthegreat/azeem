
import streamlit as st
import requests
import pandas as pd

st.set_page_config(layout="wide")
st.title("🚀 Multi Exchange Futures Scanner")

exchange = st.sidebar.selectbox(
    "Exchange",
    ["MEXC Futures","Bitget Futures","Gate Futures","Binance Futures"]
)

tf = st.sidebar.selectbox("Timeframe",["5m","15m","1h","4h","1d"])
patterns = st.sidebar.multiselect(
    "Patterns",
    ["Hammer","Inverted Hammer","Bullish Engulfing","Bearish Engulfing",
     "100 EMA","20 Candle Breakout","30 Candle Breakout",
     "RSI Divergence","Volume Bubble","SFP"],
    ["Hammer"]
)

limit = st.sidebar.number_input("Contracts",10,200,50)

st.info("Exchange selector added. MEXC adapter included. Bitget/Gate/Binance adapters can use the same interface.")

def get_mexc_symbols():
    try:
        r=requests.get(
        "https://contract.mexc.com/api/v1/contract/detail",
        timeout=10).json()
        return [x["symbol"] for x in r["data"] if x.get("quoteCoin")=="USDT"][:limit]
    except:
        return []

def get_mexc_kline(symbol, interval):
    try:
        r=requests.get(
        f"https://contract.mexc.com/api/v1/contract/kline/{symbol}",
        params={"interval":interval,"limit":120},
        timeout=10).json()

        d=r["data"]
        return pd.DataFrame({
        "open":d["open"],
        "high":d["high"],
        "low":d["low"],
        "close":d["close"],
        "volume":d["vol"]
        }).astype(float)
    except:
        return pd.DataFrame()

def hammer(df):
    x=df.iloc[-1]
    body=abs(x.close-x.open)
    lower=min(x.open,x.close)-x.low
    upper=x.high-max(x.open,x.close)
    return lower>body*2 and upper<body

if st.button("SCAN NOW"):
    if exchange!="MEXC Futures":
        st.warning("Selected exchange connector placeholder. MEXC is active in this build.")

    results=[]
    symbols=get_mexc_symbols()

    for s in symbols:
        df=get_mexc_kline(s,tf)
        if df.empty:
            continue

        signal=[]

        if "Hammer" in patterns and hammer(df):
            signal.append("Hammer")

        if signal:
            results.append({
            "Exchange":exchange,
            "Contract":s,
            "TF":tf,
            "Signal":",".join(signal),
            "Price":df.close.iloc[-1]
            })

    if results:
        st.dataframe(pd.DataFrame(results),use_container_width=True)
    else:
        st.warning("No setup found")
