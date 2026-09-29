import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go

BINANCE = "https://fapi.binance.com"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "CryptoScanner/1.0"})

CANDLE_PATTERNS = {
    "Hammer":"bull","Inverted Hammer":"bull","Shooting Star":"bear","Hanging Man":"bear",
    "Doji":"neutral","Long Legged Doji":"neutral","Dragonfly Doji":"bull","Gravestone Doji":"bear",
    "Marubozu":"neutral","Spinning Top":"neutral","Bullish Engulfing":"bull","Bearish Engulfing":"bear",
    "Bullish Harami":"bull","Bearish Harami":"bear","Piercing Line":"bull","Dark Cloud Cover":"bear",
    "Inside Bar":"neutral","Outside Bar":"neutral","Tweezer Bottom":"bull","Tweezer Top":"bear",
    "Morning Star":"bull","Evening Star":"bear","Three White Soldiers":"bull","Three Black Crows":"bear",
    "Three Inside Up":"bull","Three Inside Down":"bear","Three Outside Up":"bull","Three Outside Down":"bear",
    "Three Line Strike Bull":"bull","Three Line Strike Bear":"bear","Bullish Belt Hold":"bull",
    "Bearish Belt Hold":"bear","Bullish Kicker":"bull","Bearish Kicker":"bear","Matching Low":"bull",
    "Homing Pigeon":"bull","Rising Three Methods":"bull","Falling Three Methods":"bear",
    "Tasuki Gap Up":"bull","Tasuki Gap Down":"bear"
}
CHART_PATTERNS = {
    "Ascending Triangle":"bull","Descending Triangle":"bear","Symmetrical Triangle":"neutral",
    "Rising Wedge":"bear","Falling Wedge":"bull","Bull Flag":"bull","Bear Flag":"bear",
    "Bull Pennant":"bull","Bear Pennant":"bear","Rectangle":"neutral","Double Top":"bear",
    "Double Bottom":"bull","Triple Top":"bear","Triple Bottom":"bull","Head & Shoulders":"bear",
    "Inverse Head & Shoulders":"bull","Cup & Handle":"bull","Rounding Bottom":"bull",
    "Rounding Top":"bear","Ascending Channel":"bull","Descending Channel":"bear","Broadening Formation":"neutral"
}
TIMEFRAMES = ["5m","15m","30m","1h","4h","1d"]

@st.cache_data(ttl=15, show_spinner=False)
def get_json(path, params=None):
    r = SESSION.get(BINANCE + path, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=15, show_spinner=False)
def klines(symbol, interval, limit=150):
    data = get_json("/fapi/v1/klines", {"symbol":symbol,"interval":interval,"limit":limit})
    return [{"t":int(x[0]),"o":float(x[1]),"h":float(x[2]),"l":float(x[3]),
             "c":float(x[4]),"v":float(x[5]),"q":float(x[7]),"tbq":float(x[10])} for x in data]

def sma(values, n):
    if len(values) < n: return sum(values)/len(values) if values else 0
    return sum(values[-n:])/n

def ema(values, n=100):
    if not values: return 0
    e = values[0]; k = 2/(n+1)
    for v in values[1:]: e = v*k + e*(1-k)
    return e

def rsi(values, n=14):
    if len(values) < n+1: return None
    gains=[]; losses=[]
    for i in range(1,len(values)):
        d=values[i]-values[i-1]; gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains[:n])/n; al=sum(losses[:n])/n
    for i in range(n,len(gains)):
        ag=(ag*(n-1)+gains[i])/n; al=(al*(n-1)+losses[i])/n
    return 100 if al==0 else 100-100/(1+ag/al)

def body(x): return abs(x["c"]-x["o"])
def rng(x): return x["h"]-x["l"]

def candle_match(name,a,i):
    if i < 4: return False
    x=a[i]; p=a[i-1]; p2=a[i-2]; p3=a[i-3]
    b=body(x); r=rng(x)
    if r<=0: return False
    up=x["h"]-max(x["o"],x["c"]); dn=min(x["o"],x["c"])-x["l"]
    if name=="Hammer": return dn>=b*2 and up<=max(b*.65,r*.18) and b/r<=.45
    if name=="Inverted Hammer": return up>=b*2 and dn<=max(b*.65,r*.18) and b/r<=.45
    if name=="Shooting Star": return up>=b*2 and dn<=max(b*.65,r*.18) and x["c"]<x["o"]
    if name=="Hanging Man": return dn>=b*2 and up<=max(b*.65,r*.18) and x["c"]<x["o"]
    if name=="Doji": return b/r<=.10
    if name=="Long Legged Doji": return b/r<=.08 and r>1.3*sma([rng(z) for z in a[max(0,i-20):i]],10)
    if name=="Dragonfly Doji": return b/r<=.12 and up/r<=.12
    if name=="Gravestone Doji": return b/r<=.12 and dn/r<=.12
    if name=="Marubozu": return b/r>=.85
    if name=="Spinning Top": return b/r<=.35 and up/r>.2 and dn/r>.2
    if name=="Bullish Engulfing": return p["c"]<p["o"] and x["c"]>x["o"] and x["o"]<=p["c"] and x["c"]>=p["o"]
    if name=="Bearish Engulfing": return p["c"]>p["o"] and x["c"]<x["o"] and x["o"]>=p["c"] and x["c"]<=p["o"]
    if name=="Bullish Harami": return p["c"]<p["o"] and x["c"]>x["o"] and x["o"]>p["c"] and x["c"]<p["o"]
    if name=="Bearish Harami": return p["c"]>p["o"] and x["c"]<x["o"] and x["o"]<p["c"] and x["c"]>p["o"]
    if name=="Piercing Line": return p["c"]<p["o"] and x["c"]>x["o"] and x["c"]>(p["o"]+p["c"])/2 and x["c"]<p["o"]
    if name=="Dark Cloud Cover": return p["c"]>p["o"] and x["c"]<x["o"] and x["c"]<(p["o"]+p["c"])/2 and x["c"]>p["o"]
    if name=="Inside Bar": return x["h"]<p["h"] and x["l"]>p["l"]
    if name=="Outside Bar": return x["h"]>p["h"] and x["l"]<p["l"]
    if name=="Tweezer Bottom": return abs(x["l"]-p["l"])/x["c"]<.0015 and p["c"]<p["o"] and x["c"]>x["o"]
    if name=="Tweezer Top": return abs(x["h"]-p["h"])/x["c"]<.0015 and p["c"]>p["o"] and x["c"]<x["o"]
    if name=="Morning Star": return p2["c"]<p2["o"] and body(p)<=body(p2)*.55 and x["c"]>x["o"] and x["c"]>(p2["o"]+p2["c"])/2
    if name=="Evening Star": return p2["c"]>p2["o"] and body(p)<=body(p2)*.55 and x["c"]<x["o"] and x["c"]<(p2["o"]+p2["c"])/2
    if name=="Three White Soldiers": return all(z["c"]>z["o"] for z in (p2,p,x)) and x["c"]>p["c"]>p2["c"]
    if name=="Three Black Crows": return all(z["c"]<z["o"] for z in (p2,p,x)) and x["c"]<p["c"]<p2["c"]
    if name=="Three Inside Up": return p2["c"]<p2["o"] and p["c"]>p["o"] and p["c"]>p2["c"] and x["c"]>p["h"]
    if name=="Three Inside Down": return p2["c"]>p2["o"] and p["c"]<p["o"] and p["c"]<p2["c"] and x["c"]<p["l"]
    if name=="Three Outside Up": return p2["c"]<p2["o"] and p["c"]>p["o"] and p["o"]<=p2["c"] and p["c"]>=p2["o"] and x["c"]>p["h"]
    if name=="Three Outside Down": return p2["c"]>p2["o"] and p["c"]<p["o"] and p["o"]>=p2["c"] and p["c"]<=p2["o"] and x["c"]<p["l"]
    if name=="Bullish Belt Hold": return x["c"]>x["o"] and abs(x["o"]-x["l"])/r<.08
    if name=="Bearish Belt Hold": return x["c"]<x["o"] and abs(x["o"]-x["h"])/r<.08
    if name=="Bullish Kicker": return p["c"]<p["o"] and x["c"]>x["o"] and x["o"]>p["o"]
    if name=="Bearish Kicker": return p["c"]>p["o"] and x["c"]<x["o"] and x["o"]<p["o"]
    if name=="Matching Low": return p["c"]<p["o"] and x["c"]<x["o"] and abs(p["c"]-x["c"])/x["c"]<.0015
    if name=="Homing Pigeon": return p2["c"]<p2["o"] and p["c"]<p["o"] and body(p)<body(p2)*.65 and x["c"]>x["o"]
    if name=="Rising Three Methods": return p3["c"]>p3["o"] and p2["c"]<p2["o"] and p["c"]<p["o"] and x["c"]>x["o"] and x["c"]>p3["c"]
    if name=="Falling Three Methods": return p3["c"]<p3["o"] and p2["c"]>p2["o"] and p["c"]>p["o"] and x["c"]<x["o"] and x["c"]<p3["c"]
    return False

def latest_candle(name,a):
    for i in range(len(a)-1,max(3,len(a)-7),-1):
        if candle_match(name,a,i): return i
    return -1

def linreg(vals):
    n=len(vals)
    if n<2:return 0,vals[-1] if vals else 0
    sx=sum(range(n)); sy=sum(vals); sxx=sum(i*i for i in range(n)); sxy=sum(i*y for i,y in enumerate(vals))
    d=n*sxx-sx*sx; m=(n*sxy-sx*sy)/(d or 1); b=(sy-m*sx)/n
    return m,b

def chart_match(name,a):
    if len(a)<40:return -1
    w=a[-40:]; highs=[x["h"] for x in w]; lows=[x["l"] for x in w]; closes=[x["c"] for x in w]
    mh,_=linreg(highs); ml,_=linreg(lows); mid=closes[-1]
    atr=sum(rng(x) for x in w)/40
    hi1=max(highs[:20]); hi2=max(highs[20:]); lo1=min(lows[:20]); lo2=min(lows[20:])
    near=lambda x,y: abs(x-y)/mid<.025
    if name=="Ascending Triangle" and ml>0 and abs(mh)<atr*.015 and near(max(highs[-10:]),max(highs[-25:-10])): return len(a)-1
    if name=="Descending Triangle" and mh<0 and abs(ml)<atr*.015 and near(min(lows[-10:]),min(lows[-25:-10])): return len(a)-1
    if name=="Symmetrical Triangle" and mh<0 and ml>0: return len(a)-1
    if name=="Rising Wedge" and mh>0 and ml>0 and ml>mh*.75: return len(a)-1
    if name=="Falling Wedge" and mh<0 and ml<0 and abs(mh)>abs(ml)*.75: return len(a)-1
    if name=="Bull Flag" and closes[0]<closes[-1] and mh<0 and ml<0:return len(a)-1
    if name=="Bear Flag" and closes[0]>closes[-1] and mh<0 and ml<0:return len(a)-1
    if name=="Bull Pennant" and closes[0]<closes[-1] and mh<0 and ml>0:return len(a)-1
    if name=="Bear Pennant" and closes[0]>closes[-1] and mh<0 and ml>0:return len(a)-1
    if name=="Rectangle" and abs(mh)<atr*.01 and abs(ml)<atr*.01:return len(a)-1
    if name=="Double Top" and near(hi1,hi2) and closes[-1]<hi2*.985:return len(a)-1
    if name=="Double Bottom" and near(lo1,lo2) and closes[-1]>lo2*1.015:return len(a)-1
    if name=="Triple Top" and near(hi1,hi2) and near(max(highs[25:]),hi2) and closes[-1]<hi2*.99:return len(a)-1
    if name=="Triple Bottom" and near(lo1,lo2) and near(min(lows[25:]),lo2) and closes[-1]>lo2*1.01:return len(a)-1
    if name=="Head & Shoulders":
        q=[max(highs[:13]),max(highs[13:27]),max(highs[27:])]
        if q[1]>q[0]*1.015 and q[1]>q[2]*1.015 and near(q[0],q[2]):return len(a)-1
    if name=="Inverse Head & Shoulders":
        q=[min(lows[:13]),min(lows[13:27]),min(lows[27:])]
        if q[1]<q[0]*.985 and q[1]<q[2]*.985 and near(q[0],q[2]):return len(a)-1
    if name=="Cup & Handle":
        left=min(closes[:12]); center=min(closes[12:30]); right=min(closes[30:])
        if center<left*.97 and right>center*1.04 and closes[-1]>right*.98:return len(a)-1
    if name=="Rounding Bottom" and ml>0:return len(a)-1
    if name=="Rounding Top" and mh<0:return len(a)-1
    if name=="Ascending Channel" and mh>0 and ml>0:return len(a)-1
    if name=="Descending Channel" and mh<0 and ml<0:return len(a)-1
    if name=="Broadening Formation" and mh>0 and ml<0:return len(a)-1
    return -1

def levels(a):
    prev=a[-36:-1]
    hi=max(x["h"] for x in prev); lo=min(x["l"] for x in prev); p=a[-1]["c"]
    if abs(p-lo)/p<=.008:return "Support",lo
    if abs(p-hi)/p<=.008:return "Resistance",hi
    return "Middle",lo if abs(p-lo)<abs(p-hi) else hi

def volinfo(a):
    x=a[-1]; avg=sma([z["v"] for z in a[-21:-1]],20) or x["v"]; ratio=x["v"]/avg
    buy=x["tbq"]/x["q"]*100 if x["q"] else 50
    return ratio,buy,"Bull" if buy>=50 else "Bear"

def sfp(a):
    x=a[-1]; prev=a[-21:-1]; ph=max(z["h"] for z in prev); pl=min(z["l"] for z in prev)
    if x["l"]<pl and x["c"]>prev[-1]["c"]:return "Bullish SFP",pl,"Bull"
    if x["h"]>ph and x["c"]<prev[-1]["c"]:return "Bearish SFP",ph,"Bear"
    return None

def divergence(a):
    c=[z["c"] for z in a]; n=len(c); lows=[]; highs=[]
    for i in range(max(2,n-28),n-2):
        if c[i]<c[i-1] and c[i]<c[i+1]:lows.append(i)
        if c[i]>c[i-1] and c[i]>c[i+1]:highs.append(i)
    if len(lows)>=2:
        i,j=lows[-2],lows[-1]; r1=rsi(c[:i+1]);r2=rsi(c[:j+1])
        if r1 is not None and r2 is not None and c[j]<c[i] and r2>r1+2:return "Bullish RSI Divergence",r2
    if len(highs)>=2:
        i,j=highs[-2],highs[-1]; r1=rsi(c[:i+1]);r2=rsi(c[:j+1])
        if r1 is not None and r2 is not None and c[j]>c[i] and r2<r1-2:return "Bearish RSI Divergence",r2
    return None

@st.cache_data(ttl=30, show_spinner=False)
def funding_oi(symbol):
    try:
        p=get_json("/fapi/v1/premiumIndex",{"symbol":symbol})
        o=get_json("/fapi/v1/openInterest",{"symbol":symbol})
        hist=get_json("/futures/data/openInterestHist",{"symbol":symbol,"period":"5m","limit":30})
        old=float(hist[0]["sumOpenInterest"]) if hist else None
        cur=float(o["openInterest"])
        ch=(cur-old)/old*100 if old else None
        return float(p["lastFundingRate"])*100,ch
    except Exception:
        return None,None

def scan_symbol(symbol, mode, pattern, tf, opts):
    try:
        a=klines(symbol,tf,150); closed=a[:-1]; live=a[-1]
        ratio,buy,vol_dir=volinfo(a); ema100=ema([z["c"] for z in a],100); loc,level=levels(a)
        base={"symbol":symbol,"tf":tf,"price":live["c"],"ema100":ema100,"volume_ratio":ratio,"location":loc,"level":level}
        if mode=="candles":
            idx=latest_candle(pattern,a); live_hit=candle_match(pattern,a,len(a)-1)
            if live_hit and opts.get("forming",True):
                return {**base,"setup":pattern,"state":"FORMING NOW","direction":CANDLE_PATTERNS[pattern],"key":"Live candle","index":len(a)-1,"candles":a[-80:]}
            if idx>=0 and opts.get("recent",True) and (not opts.get("only_sr",True) or loc!="Middle"):
                return {**base,"setup":pattern,"state":"JUST FORMED" if idx==len(a)-2 else "RECENT","direction":CANDLE_PATTERNS[pattern],"key":f"{len(a)-1-idx} candle ago","index":idx,"candles":a[-80:]}
        elif mode=="charts":
            idx=chart_match(pattern,closed)
            if idx>=0:return {**base,"setup":pattern,"state":"FORMING","direction":CHART_PATTERNS[pattern],"key":"Latest structure","index":len(a)-2,"candles":a[-80:]}
        elif mode=="ema":
            dist=(live["c"]-ema100)/ema100*100; crossed=(closed[-1]["c"]-ema100)*(closed[-2]["c"]-ema100)<0
            if abs(dist)<=1.2 or crossed:return {**base,"setup":"4H 100 EMA "+("RETEST" if abs(dist)<=1.2 else "CROSS"),"state":"RETEST ZONE" if abs(dist)<=1.2 else "CROSS","direction":"Bull" if dist>=0 else "Bear","key":f"{dist:.2f}% from EMA","index":len(a)-1,"candles":a[-80:]}
        elif mode=="breakout":
            h20=max(z["h"] for z in closed[-20:]);l20=min(z["l"] for z in closed[-20:]);h30=max(z["h"] for z in closed[-30:]);l30=min(z["l"] for z in closed[-30:])
            bull=live["c"]>h20 or live["c"]>h30; bear=live["c"]<l20 or live["c"]<l30
            if (bull or bear) and (not opts.get("volume_confirm") or ratio>=1.5):
                n=30 if (live["c"]>h30 if bull else live["c"]<l30) else 20
                return {**base,"setup":f"{n} Candle "+("Breakout" if bull else "Breakdown"),"state":"CONFIRMED CLOSE","direction":"Bull" if bull else "Bear","key":f"Vol {ratio:.1f}x","index":len(a)-1,"candles":a[-80:]}
        elif mode=="funding":
            fr,oi_ch=funding_oi(symbol)
            if fr is not None and oi_ch is not None and fr<0 and oi_ch>0:
                return {**base,"setup":"Negative Funding + Rising OI","state":"SHORT CROWD","direction":"Bull","key":f"{fr:.3f}% / OI +{oi_ch:.1f}%","funding":fr,"oi_change":oi_ch,"index":len(a)-1,"candles":a[-80:]}
        elif mode=="sfp":
            s=sfp(closed)
            if s:return {**base,"setup":s[0],"state":"LIQUIDITY SWEEP","direction":s[2],"key":f"Sweep {s[1]:.6g}","index":len(a)-2,"candles":a[-80:]}
        elif mode=="strength":
            if symbol=="BTCUSDT":return None
            btc=klines("BTCUSDT",tf,40); alt=(live["c"]/a[-11]["c"]-1)*100; br=(btc[-1]["c"]/btc[-11]["c"]-1)*100; rs=alt-br
            if abs(rs)>=1.5:return {**base,"setup":"ALT vs BTC Relative Strength","state":"STRONGER" if rs>0 else "WEAKER","direction":"Bull" if rs>0 else "Bear","key":f"RS {rs:.2f}%","rs":rs,"index":len(a)-1,"candles":a[-80:]}
        elif mode=="volume":
            if ratio>=2:return {**base,"setup":"Volume Bubble — "+vol_dir,"state":"LARGE FLOW","direction":vol_dir,"key":f"{ratio:.1f}x / Buy {buy:.0f}%","index":len(a)-1,"candles":a[-80:]}
        elif mode=="rsi":
            d=divergence(closed)
            if d:return {**base,"setup":d[0],"state":"DIVERGENCE","direction":"Bull" if d[0].startswith("Bull") else "Bear","key":f"RSI {d[1]:.1f}","index":len(a)-2,"candles":a[-80:]}
    except Exception:
        return None
    return None

@st.cache_data(ttl=30, show_spinner=False)
def universe(n):
    data=get_json("/fapi/v1/ticker/24hr")
    rows=[x for x in data if x["symbol"].endswith("USDT") and "_" not in x["symbol"]]
    rows.sort(key=lambda x:float(x.get("quoteVolume",0)),reverse=True)
    return [x["symbol"] for x in rows[:n]]

def scan_all(symbols, mode, pattern, tf, opts):
    results=[]
    workers=min(10,max(4,len(symbols)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs=[ex.submit(scan_symbol,s,mode,pattern,tf,opts) for s in symbols]
        for f in as_completed(futs):
            try:
                r=f.result()
                if r: results.append(r)
            except Exception:
                pass
    results.sort(key=lambda x:(0 if x["state"] in ("FORMING NOW","FORMING") else 1, -float(x.get("volume_ratio",0))))
    return results

def chart_for(result):
    rows=result["candles"]
    df=pd.DataFrame(rows)
    df["time"]=pd.to_datetime(df["t"],unit="ms")
    fig=go.Figure(go.Candlestick(x=df["time"],open=df["o"],high=df["h"],low=df["l"],close=df["c"],name=result["symbol"]))
    idx=min(max(int(result.get("index",len(df)-1))-(len(rows)-80),0),len(df)-1)
    t=df.iloc[idx]["time"]
    fig.add_vline(x=t,line_width=2,line_dash="dash")
    if result.get("ema100"):
        closes=df["c"].tolist(); ema_vals=[]; e=closes[0]; k=2/(101)
        for v in closes:
            e=v*k+e*(1-k); ema_vals.append(e)
        fig.add_trace(go.Scatter(x=df["time"],y=ema_vals,mode="lines",name="100 EMA"))
    fig.update_layout(height=520,margin=dict(l=10,r=10,t=40,b=10),xaxis_rangeslider_visible=False,title=f'{result["symbol"]} · {result["setup"]}')
    return fig

st.set_page_config(page_title="Binance Futures Crypto Scanner", page_icon="📊", layout="wide")
st.title("📊 Binance Futures Crypto Scanner")
st.caption("Candles • Chart Patterns • 100 EMA • Breakouts • Funding/OI • SFP • Relative Strength • Volume • RSI Divergence")

with st.sidebar:
    st.header("Scanner Settings")
    mode_label=st.selectbox("Scanner", [
        "Candle Pattern","Chart Pattern","4H 100 EMA","20/30 Candle Breakout","Negative Funding + Rising OI",
        "Swing Failure Pattern (SFP)","Alt vs BTC Relative Strength","Volume Bubble","RSI Divergence"])
    mode_map={
        "Candle Pattern":"candles","Chart Pattern":"charts","4H 100 EMA":"ema","20/30 Candle Breakout":"breakout",
        "Negative Funding + Rising OI":"funding","Swing Failure Pattern (SFP)":"sfp","Alt vs BTC Relative Strength":"strength",
        "Volume Bubble":"volume","RSI Divergence":"rsi"}
    mode=mode_map[mode_label]
    tf=st.selectbox("Timeframe", TIMEFRAMES, index=1)
    universe_n=st.selectbox("Coins to scan", [30,50,80,100], index=1)
    if mode=="candles":
        pattern=st.selectbox("Candle Pattern", list(CANDLE_PATTERNS.keys()))
        forming=st.checkbox("Include forming/current candle", True)
        recent=st.checkbox("Include recent closed candles", True)
        only_sr=st.checkbox("Support/Resistance only", True)
    elif mode=="charts":
        pattern=st.selectbox("Chart Pattern", list(CHART_PATTERNS.keys()))
    else:
        pattern=""
    volume_confirm=False
    if mode=="breakout": volume_confirm=st.checkbox("Require volume confirmation (≥ 1.5x)", True)
    auto=st.checkbox("Auto refresh", False)
    refresh_sec=st.slider("Refresh seconds", 15, 180, 60, 15) if auto else 60
    scan=st.button("🔎 Scan Now", type="primary", use_container_width=True)

if scan or "results" not in st.session_state:
    opts={"forming":locals().get("forming",True),"recent":locals().get("recent",True),"only_sr":locals().get("only_sr",True),"volume_confirm":volume_confirm}
    with st.spinner(f"Scanning top {universe_n} Binance USDT futures…"):
        try:
            symbols=universe(universe_n)
            results=scan_all(symbols,mode,pattern,tf,opts)
            st.session_state.results=results
            st.session_state.scanned=len(symbols)
            st.session_state.scan_time=time.time()
            st.session_state.scan_mode=mode_label
        except Exception as e:
            st.error(f"Binance API error: {e}")
            results=[]
else:
    results=st.session_state.results

if auto and st.session_state.get("scan_time") and time.time()-st.session_state.scan_time>=refresh_sec:
    st.rerun()

results=st.session_state.get("results",[])
scanned=st.session_state.get("scanned",universe_n)

c1,c2,c3,c4=st.columns(4)
c1.metric("Coins Scanned", scanned)
c2.metric("Signals", len(results))
c3.metric("Bullish", sum(r.get("direction")=="Bull" for r in results))
c4.metric("Bearish", sum(r.get("direction")=="Bear" for r in results))

if not results:
    st.info("No matching setup found. Try another timeframe, pattern, or disable Support/Resistance-only filter.")
else:
    display=[]
    for r in results:
        display.append({
            "Coin":r["symbol"],"Setup":r["setup"],"State":r["state"],"Direction":r["direction"],
            "Location":r.get("location","-"),"Level":r.get("level","-"),"Price":r.get("price",0),"Key":r.get("key","-"),
            "Vol x":round(r.get("volume_ratio",0),2)
        })
    st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)
    names=[f'{r["symbol"]} · {r["setup"]}' for r in results]
    selected=st.selectbox("Chart preview", names)
    selected_result=results[names.index(selected)]
    st.plotly_chart(chart_for(selected_result), use_container_width=True)
    st.write({k:v for k,v in selected_result.items() if k!="candles"})

st.divider()
st.caption("Note: advanced chart patterns, SFP, RSI divergence and volume bubbles are rule-based approximations. Volume Bubble uses candle/taker-buy volume as a proxy, not true order-by-order footprint data. Binance public Futures API is used; no API key is required for these endpoints.")
