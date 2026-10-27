from __future__ import annotations

from datetime import date, datetime, timedelta
import os
import math
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Global Market Radar", page_icon="🌐", layout="wide")

st.title("🌐 Global Market Radar")
st.caption("글로벌 매크로 · 한국 시장 대시보드 | 교육·연구용 프로토타입 — 주문 실행 기능 없음")

# These are public Yahoo Finance symbols, not guaranteed real-time exchange feeds.
ASSETS = {
    "미국 나스닥 선물 (NQ)": "NQ=F",
    "미국 다우 선물 (YM)": "YM=F",
    "독일 DAX 선물 (FDAX)": "FDAX=F",
    "중국 상하이종합 (현물 대리)": "000001.SS",
    "홍콩 항셍 (현물 대리)": "^HSI",
    "VIX": "^VIX",
    "달러인덱스 (DXY 대리)": "DX-Y.NYB",
    "원/달러 환율": "KRW=X",
    "WTI 원유 선물": "CL=F",
    "미국 10년물 금리 (^TNX)": "^TNX",
    "코스피 종합지수": "^KS11",
    "코스닥 종합지수": "^KQ11",
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "현대차": "005380.KS",
    "KB금융": "105560.KS",
}

TREND_GROUPS = {
    "글로벌 지수/선물": ["미국 나스닥 선물 (NQ)", "미국 다우 선물 (YM)", "독일 DAX 선물 (FDAX)", "중국 상하이종합 (현물 대리)", "홍콩 항셍 (현물 대리)"],
    "변동성": ["VIX"],
    "환율": ["달러인덱스 (DXY 대리)", "원/달러 환율"],
    "원자재·금리": ["WTI 원유 선물", "미국 10년물 금리 (^TNX)"],
    "한국 시장": ["코스피 종합지수", "코스닥 종합지수"],
    "대형주": ["삼성전자", "SK하이닉스", "현대차", "KB금융"],
}

def safe_history(symbol: str, start: date, end_exclusive: date, interval: str) -> pd.DataFrame:
    try:
        df = yf.Ticker(symbol).history(
            start=start.isoformat(),
            end=end_exclusive.isoformat(),
            interval=interval,
            auto_adjust=False,
            actions=False,
            prepost=(interval != "1d"),
            timeout=15,
        )
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.dropna(subset=["Close"])
        return df
    except Exception:
        return pd.DataFrame()

def classify_change(pct: float | None, threshold: float = 0.5) -> str:
    if pct is None or pd.isna(pct):
        return "데이터 없음"
    if pct >= threshold:
        return "상승"
    if pct <= -threshold:
        return "하락"
    return "횡보"

def pct_change(df: pd.DataFrame, bars: int = 5) -> float | None:
    if df.empty or len(df) < 2:
        return None
    close = pd.to_numeric(df["Close"], errors="coerce").dropna()
    if len(close) < 2:
        return None
    first = close.iloc[max(0, len(close) - bars - 1)]
    last = close.iloc[-1]
    if not first or pd.isna(first) or pd.isna(last):
        return None
    return float((last / first - 1) * 100)

def fmt_num(v, digits=2):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.{digits}f}"

def trend_for(name: str, pct: float | None) -> str:
    # Direction thresholds differ by asset class.
    threshold = 0.25 if ("금리" in name or "VIX" in name) else 0.5
    return classify_change(pct, threshold)

def weighted_market_score(rows: list[dict]) -> tuple[int | None, str, list[str]]:
    # A deliberately transparent, coarse heuristic; NOT a validated trading strategy.
    score, weight_sum, positives, negatives = 0.0, 0.0, [], []
    # Direction should be interpreted contextually, not mechanically.
    signs = {
        "미국 나스닥 선물 (NQ)": 1, "미국 다우 선물 (YM)": 1,
        "독일 DAX 선물 (FDAX)": 1, "중국 상하이종합 (현물 대리)": 1,
        "홍콩 항셍 (현물 대리)": 1, "VIX": -1,
        "달러인덱스 (DXY 대리)": -1, "원/달러 환율": -1,
        "WTI 원유 선물": 0, "미국 10년물 금리 (^TNX)": 0,
        "코스피 종합지수": 1, "코스닥 종합지수": 1,
    }
    weights = {
        "미국 나스닥 선물 (NQ)": 1.3, "미국 다우 선물 (YM)": 1.0,
        "독일 DAX 선물 (FDAX)": 0.7, "중국 상하이종합 (현물 대리)": 0.6,
        "홍콩 항셍 (현물 대리)": 0.7, "VIX": 1.2,
        "달러인덱스 (DXY 대리)": 0.8, "원/달러 환율": 1.0,
        "코스피 종합지수": 1.4, "코스닥 종합지수": 0.8,
    }
    for row in rows:
        name, trend = row["항목"], row["방향"]
        if name not in signs or signs[name] == 0 or trend not in ("상승", "하락"):
            continue
        w = weights.get(name, 1.0)
        direction = 1 if trend == "상승" else -1
        contribution = direction * signs[name]
        score += contribution * w
        weight_sum += w
        if contribution > 0:
            positives.append(name)
        else:
            negatives.append(name)
    if weight_sum == 0:
        return None, "판단 불가", []
    normalized = (score / weight_sum + 1) * 50
    score100 = max(0, min(100, round(normalized)))
    if score100 >= 70:
        label = "매수 우위 검토"
    elif score100 >= 55:
        label = "선별 매수"
    elif score100 >= 40:
        label = "중립·관망"
    else:
        label = "방어 모드"
    return score100, label, positives + ["—"] + negatives

with st.sidebar:
    st.header("분석 설정")
    selected_date = st.date_input("분석 날짜", value=date.today(), max_value=date.today())
    mode = st.radio("분석 모드", ["과거 복기 / 장 마감", "장중 참고 (지연 가능)"])
    lookback = st.selectbox("추세 비교 기준", ["최근 5개 관측치", "최근 20개 관측치"], index=0)
    interval = "1d" if mode == "과거 복기 / 장 마감" else "5m"
    bars = 5 if lookback.startswith("최근 5") else 20
    st.markdown("---")
    st.caption("무료 시세는 지연·누락·심볼 변경이 있을 수 있습니다. 체결 판단용으로 사용하지 마세요.")

today = date.today()
if interval != "1d" and (today - selected_date).days > 59:
    st.warning("Yahoo Finance 무료 장중 데이터는 최근 약 60일 범위로 제한될 수 있어요. 오래된 날짜는 '과거 복기 / 장 마감'을 선택하세요.")

if interval == "1d":
    start_date = selected_date - timedelta(days=max(45, bars * 3))
    end_date = selected_date + timedelta(days=1)
else:
    start_date = selected_date
    end_date = selected_date + timedelta(days=1)

@st.cache_data(ttl=180, show_spinner=False)
def load_all(start_iso: str, end_iso: str, interval_arg: str):
    out = {}
    for name, symbol in ASSETS.items():
        out[name] = safe_history(symbol, date.fromisoformat(start_iso), date.fromisoformat(end_iso), interval_arg)
    return out

with st.spinner("시장 데이터를 불러오는 중입니다..."):
    all_data = load_all(start_date.isoformat(), end_date.isoformat(), interval)

# For historical mode, only use observations on or before the selected date.
rows = []
for name, symbol in ASSETS.items():
    df = all_data.get(name, pd.DataFrame())
    if not df.empty:
        df = df.loc[df.index.date <= selected_date]
    change = pct_change(df, bars=bars) if not df.empty else None
    latest = float(df["Close"].iloc[-1]) if not df.empty else None
    rows.append({
        "항목": name,
        "심볼": symbol,
        "최근값": latest,
        "변화율(%)": change,
        "방향": trend_for(name, change),
        "관측시각": str(df.index[-1]) if not df.empty else "데이터 없음",
        "data": df,
    })

rows_by_name = {r["항목"]: r for r in rows}
score, label, contributors = weighted_market_score(rows)

# Header cards
c1, c2, c3 = st.columns(3)
c1.metric("종합 점수 (초기 규칙)", f"{score}/100" if score is not None else "—")
c2.metric("시장 모드", label)
valid = sum(1 for r in rows if r["변화율(%)"] is not None)
c3.metric("데이터 수집", f"{valid}/{len(rows)} 항목")
st.caption("점수는 방향 신호의 단순 가중합입니다. 경제지표·뉴스·수급·차트 패턴을 모두 반영한 완성 모델이 아니며, 투자 권유가 아닙니다.")

if score is not None and score < 40:
    st.error("위험 경고: 현재 규칙상 방어 모드입니다. 점수만으로 매도·매수를 결정하지 마세요.")
elif score is not None and score >= 70:
    st.success("긍정 신호가 상대적으로 우세합니다. 그래도 가격 위치·수급·손절 기준을 별도로 확인하세요.")
else:
    st.info("방향 신호만으로 강한 매수 결론을 내리기 어렵습니다. 이벤트와 수급 확인이 필요합니다.")

st.subheader("1. 글로벌·매크로 대시보드")
for group, names in TREND_GROUPS.items():
    with st.expander(group, expanded=(group in ["글로벌 지수/선물", "한국 시장", "변동성"])):
        table_rows = []
        for name in names:
            r = rows_by_name[name]
            table_rows.append({
                "항목": name,
                "최근값": fmt_num(r["최근값"]),
                f"{bars}개 관측치 변화율": f'{fmt_num(r["변화율(%)"])}%' if r["변화율(%)"] is not None else "—",
                "방향": r["방향"],
                "데이터 시각": r["관측시각"],
                "심볼": r["심볼"],
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

st.subheader("2. 지수·대형주 차트")
chart_names = st.multiselect(
    "차트에 표시할 항목",
    options=list(ASSETS.keys()),
    default=["미국 나스닥 선물 (NQ)", "VIX", "원/달러 환율", "WTI 원유 선물", "코스피 종합지수", "삼성전자", "SK하이닉스"],
)
for name in chart_names:
    df = all_data.get(name, pd.DataFrame())
    if not df.empty:
        df = df.loc[df.index.date <= selected_date]
        if not df.empty:
            st.markdown(f"**{name}** · {ASSETS[name]}")
            st.line_chart(df[["Close"]].rename(columns={"Close": name}), height=180)
    else:
        st.caption(f"{name}: 해당 날짜에 데이터를 받지 못했습니다.")

st.subheader("3. 경제지표·FOMC 해석")
st.warning(
    "이 첫 버전은 FOMC 발표문, CPI·고용의 실제치/예상치, 발표 시각을 자동 수집하지 않습니다. "
    "아래 항목을 공식 발표와 대조한 뒤 기록하세요. 이후 버전에서 FRED/경제 캘린더 연동을 추가할 수 있습니다."
)
event_text = st.text_area(
    "해당 날짜의 경제 이벤트 메모",
    placeholder="예: CPI 실제치 / 시장 예상치 / 이전치, 고용지표, FOMC 발언, 발표 후 2년물·10년물·달러 반응",
    height=110,
)
if event_text.strip():
    st.write("기록된 이벤트 메모:")
    st.write(event_text)

st.subheader("4. 한국 외국인·기관 수급")
st.info(
    "이 프로토타입은 KRX 외국인·기관 순매수 데이터를 아직 자동 연동하지 않습니다. "
    "일별 수급은 KRX 정보데이터시스템 또는 적법하게 이용 가능한 공급처에서 확인하세요. "
    "다음 버전에서는 pykrx 연결을 별도 모듈로 추가할 수 있지만, 스크래핑 차단·지연·약관 변경에 대비해야 합니다."
)

st.subheader("5. 오늘의 간단한 판독")
valid_rows = [r for r in rows if r["방향"] in ("상승", "하락", "횡보")]
up = sum(r["방향"] == "상승" for r in valid_rows)
down = sum(r["방향"] == "하락" for r in valid_rows)
flat = sum(r["방향"] == "횡보" for r in valid_rows)
a, b, c = st.columns(3)
a.metric("상승", up)
b.metric("하락", down)
c.metric("횡보", flat)
st.markdown(
    f"""
- 분석 날짜: **{selected_date.isoformat()}**
- 추세 비교: **최근 {bars}개 관측치**
- 수집된 항목 중 상승: **{up}**, 하락: **{down}**, 횡보: **{flat}**
- 1차 판독: **{label}**
"""
)
st.caption(
    "중요: 미국 선물·해외 지수는 서로 다른 거래시간과 휴장일을 가집니다. "
    "중국 지수 항목은 선물이 아니라 현물 지수 대리값이며, FDAX·DXY 등은 심볼 가용성에 따라 실패할 수 있습니다. "
    "이 프로그램은 데이터가 비어 있거나 지연될 수 있으며, 매매 주문을 제출하지 않습니다."
)

with st.expander("데이터 출처 및 한계"):
    st.markdown("""
- Yahoo Finance 공개 시세를 `yfinance`로 조회합니다. 연구·개인용 참고 자료이며 공식 실시간 체결 피드가 아닙니다.
- Yahoo 심볼은 변경되거나 특정 지역·계정에서 조회되지 않을 수 있습니다.
- 과거 날짜 조회는 종가 기준이며, 장중 데이터는 최근 기간만 가능할 수 있습니다.
- 이 버전은 공식 경제 캘린더의 예상치/실제치 비교, KRX 투자자별 수급, VKOSPI를 아직 자동화하지 않았습니다.
- 점수는 검증된 예측 모델이 아닙니다. 실거래 전 별도 백테스트와 데이터 검증이 필요합니다.
""")
