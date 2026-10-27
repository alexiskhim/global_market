from __future__ import annotations

from datetime import date, timedelta
import io
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Global Market Radar", page_icon="🌐", layout="wide")
st.title("🌐 Global Market Radar")
st.caption("글로벌 매크로 · 한국 시장 분석 | 최종 프로토타입 v3 · 연구/교육용 · 자동 주문 없음")

# Public Yahoo Finance symbols are convenience proxies, not guaranteed real-time exchange feeds.
ASSETS = {
    "나스닥 선물 (NQ)": "NQ=F",
    "다우 선물 (YM)": "YM=F",
    "독일 DAX 선물 (FDAX)": "FDAX=F",
    "중국 상하이종합 (현물 대리)": "000001.SS",
    "홍콩 항셍 (현물 대리)": "^HSI",
    "VIX": "^VIX",
    "한국 VKOSPI (가능 시)": "^VKOSPI",
    "달러인덱스 (DXY 대리)": "DX-Y.NYB",
    "원/달러 환율": "KRW=X",
    "WTI 원유 선물": "CL=F",
    "브렌트유 선물": "BZ=F",
    "미국 10년물 금리 (^TNX)": "^TNX",
    "코스피 종합지수": "^KS11",
    "코스닥 종합지수": "^KQ11",
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "현대차": "005380.KS",
    "KB금융": "105560.KS",
}
GROUPS = {
    "글로벌 지수/선물": ["나스닥 선물 (NQ)", "다우 선물 (YM)", "독일 DAX 선물 (FDAX)", "중국 상하이종합 (현물 대리)", "홍콩 항셍 (현물 대리)"],
    "변동성": ["VIX", "한국 VKOSPI (가능 시)"],
    "환율": ["달러인덱스 (DXY 대리)", "원/달러 환율"],
    "원자재·금리": ["WTI 원유 선물", "브렌트유 선물", "미국 10년물 금리 (^TNX)"],
    "한국 시장": ["코스피 종합지수", "코스닥 종합지수"],
    "대형주": ["삼성전자", "SK하이닉스", "현대차", "KB금융"],
}
FRED_SERIES = {
    "CPI (소비자물가지수, 월간)": ("CPIAUCSL", "index"),
    "실업률": ("UNRATE", "%"),
    "연방기금금리": ("DFF", "%"),
    "미국 10년물 금리": ("DGS10", "%"),
    "비농업 고용자 수": ("PAYEMS", "thousands"),
    "PCE 물가지수": ("PCEPI", "index"),
}

def get_history(symbol: str, start: date, end: date, interval: str) -> pd.DataFrame:
    try:
        df = yf.Ticker(symbol).history(
            start=start.isoformat(), end=end.isoformat(), interval=interval,
            auto_adjust=False, actions=False, prepost=(interval != "1d"), timeout=15
        )
        if df is None or df.empty:
            return pd.DataFrame()
        return df.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()

def change_pct(df: pd.DataFrame, bars: int) -> float | None:
    if df.empty:
        return None
    s = pd.to_numeric(df["Close"], errors="coerce").dropna()
    if len(s) < 2:
        return None
    first, last = s.iloc[max(0, len(s) - bars - 1)], s.iloc[-1]
    if pd.isna(first) or pd.isna(last) or first == 0:
        return None
    return float((last / first - 1) * 100)

def classify(v: float | None, threshold: float) -> str:
    if v is None or pd.isna(v):
        return "데이터 없음"
    if v >= threshold:
        return "상승"
    if v <= -threshold:
        return "하락"
    return "횡보"

def fmt(v, digits=2):
    return "—" if v is None or pd.isna(v) else f"{v:,.{digits}f}"

@st.cache_data(ttl=180, show_spinner=False)
def load_market_data(start_iso: str, end_iso: str, interval: str):
    result = {}
    for name, symbol in ASSETS.items():
        result[name] = get_history(symbol, date.fromisoformat(start_iso), date.fromisoformat(end_iso), interval)
    return result

def load_fred_series(api_key: str, series_id: str, start_date: date, end_date: date) -> pd.DataFrame:
    import requests
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id, "api_key": api_key, "file_type": "json",
        "observation_start": start_date.isoformat(), "observation_end": end_date.isoformat(),
    }
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    observations = response.json().get("observations", [])
    df = pd.DataFrame(observations)
    if df.empty:
        return df
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    return df[["date", "value"]]

def normalize_flow_csv(uploaded) -> tuple[pd.DataFrame | None, str | None]:
    try:
        raw = pd.read_csv(uploaded)
    except Exception as e:
        return None, f"CSV를 읽을 수 없습니다: {e}"
    lookup = {str(c).strip().lower(): c for c in raw.columns}
    date_col = next((lookup[k] for k in ["date", "날짜", "일자", "trading_date"] if k in lookup), None)
    investor_col = next((lookup[k] for k in ["investor", "투자자", "투자자구분", "주체"] if k in lookup), None)
    value_col = next((lookup[k] for k in ["net_buy", "순매수", "순매수금액", "순매수대금", "순매수량"] if k in lookup), None)
    market_col = next((lookup[k] for k in ["market", "시장", "상품", "구분"] if k in lookup), None)
    if not (date_col and investor_col and value_col):
        return None, "열 이름을 인식하지 못했습니다. 최소한 date, investor, net_buy 열이 필요합니다."
    rename = {date_col: "date", investor_col: "investor", value_col: "net_buy"}
    if market_col:
        rename[market_col] = "market"
    df = raw.rename(columns=rename)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["net_buy"] = pd.to_numeric(df["net_buy"].astype(str).str.replace(",", "", regex=False), errors="coerce")
    df = df.dropna(subset=["date", "net_buy"])
    df["investor"] = df["investor"].astype(str).str.strip()
    if "market" not in df:
        df["market"] = "미분류"
    df["market"] = df["market"].astype(str).str.strip()
    return df, None

def sentiment_score(rows: list[dict], flow_df: pd.DataFrame | None):
    # Score uses only directional market proxies. Oil and yields are contextual, not mechanically positive/negative.
    signs = {
        "나스닥 선물 (NQ)": 1, "다우 선물 (YM)": 1, "독일 DAX 선물 (FDAX)": 1,
        "중국 상하이종합 (현물 대리)": 1, "홍콩 항셍 (현물 대리)": 1,
        "VIX": -1, "한국 VKOSPI (가능 시)": -1,
        "달러인덱스 (DXY 대리)": -1, "원/달러 환율": -1,
        "코스피 종합지수": 1, "코스닥 종합지수": 1,
    }
    weights = {
        "나스닥 선물 (NQ)": 1.3, "다우 선물 (YM)": 1.0, "독일 DAX 선물 (FDAX)": .7,
        "중국 상하이종합 (현물 대리)": .6, "홍콩 항셍 (현물 대리)": .7,
        "VIX": 1.2, "한국 VKOSPI (가능 시)": .8,
        "달러인덱스 (DXY 대리)": .8, "원/달러 환율": 1.0,
        "코스피 종합지수": 1.4, "코스닥 종합지수": .8,
    }
    total, weight = 0.0, 0.0
    for row in rows:
        name, trend = row["항목"], row["방향"]
        if name in signs and trend in ("상승", "하락"):
            total += (1 if trend == "상승" else -1) * signs[name] * weights[name]
            weight += weights[name]
    # No automatic score bonus from uploaded flows yet; only show flow separately until product/market mappings are verified.
    score = round(max(0, min(100, (total / weight + 1) * 50))) if weight else None
    label = "판단 불가" if score is None else "매수 우위 검토" if score >= 70 else "선별 매수" if score >= 55 else "중립·관망" if score >= 40 else "방어 모드"
    return score, label

with st.sidebar:
    st.header("분석 설정")
    selected_date = st.date_input("분석 기준 날짜", value=date.today(), max_value=date.today())
    mode = st.radio("분석 모드", ["과거 복기 / 장 마감", "장중 참고 (지연 가능)"])
    bars = st.selectbox("추세 비교 기준", [5, 20], format_func=lambda x: f"최근 {x}개 관측치")
    interval = "1d" if mode == "과거 복기 / 장 마감" else "5m"
    st.caption("무료 공개 시세는 지연·누락될 수 있으며 공식 실시간 체결 피드가 아닙니다.")

start = selected_date - timedelta(days=max(70, bars * 4)) if interval == "1d" else selected_date
end = selected_date + timedelta(days=1)
with st.spinner("시장 데이터를 조회하고 있습니다..."):
    market_data = load_market_data(start.isoformat(), end.isoformat(), interval)

rows = []
for name, symbol in ASSETS.items():
    df = market_data.get(name, pd.DataFrame())
    if not df.empty:
        df = df.loc[df.index.date <= selected_date]
    ch = change_pct(df, bars) if not df.empty else None
    last = float(df["Close"].iloc[-1]) if not df.empty else None
    threshold = .25 if ("VIX" in name or "VKOSPI" in name or "금리" in name) else .5
    rows.append({
        "항목": name, "심볼": symbol, "최근값": last, "변화율(%)": ch,
        "방향": classify(ch, threshold), "관측시각": str(df.index[-1]) if not df.empty else "데이터 없음"
    })
by_name = {r["항목"]: r for r in rows}

# User uploads are parsed later; market score remains independent of unverified flow CSV mappings.
score, label = sentiment_score(rows, None)
c1, c2, c3 = st.columns(3)
c1.metric("종합 점수 (초기 규칙)", f"{score}/100" if score is not None else "—")
c2.metric("시장 모드", label)
c3.metric("시세 수집", f'{sum(r["변화율(%)"] is not None for r in rows)}/{len(rows)}')
st.caption("점수는 방향 신호의 단순 가중합이며 예측 확률이 아닙니다. 수급·경제지표 이벤트는 별도 영역에서 확인해야 합니다.")
if score is not None and score < 40:
    st.error("방어 모드: 신규 진입보다 위험 관리와 추가 확인을 우선하세요.")
elif score is not None and score >= 70:
    st.success("긍정 신호가 상대적으로 우세합니다. 그래도 수급·가격 위치·손절 기준을 확인하세요.")
else:
    st.info("현재 점수만으로 강한 매수 결론을 내리기 어렵습니다.")

st.subheader("1. 글로벌·매크로 대시보드")
for group, names in GROUPS.items():
    with st.expander(group, expanded=group in ["글로벌 지수/선물", "변동성", "한국 시장"]):
        table = []
        for name in names:
            r = by_name[name]
            table.append({
                "항목": name, "최근값": fmt(r["최근값"]),
                f"최근 {bars}개 변화율": f'{fmt(r["변화율(%)"])}%' if r["변화율(%)"] is not None else "—",
                "방향": r["방향"], "관측시각": r["관측시각"], "심볼": r["심볼"]
            })
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

st.subheader("2. 지수·대형주 차트")
selected_assets = st.multiselect("차트에 표시할 항목", list(ASSETS.keys()),
    default=["나스닥 선물 (NQ)", "VIX", "원/달러 환율", "WTI 원유 선물", "코스피 종합지수", "삼성전자", "SK하이닉스"])
for name in selected_assets:
    df = market_data.get(name, pd.DataFrame())
    if not df.empty:
        df = df.loc[df.index.date <= selected_date]
        if not df.empty:
            st.markdown(f"**{name}** · {ASSETS[name]}")
            st.line_chart(df[["Close"]].rename(columns={"Close": name}), height=180)
    else:
        st.caption(f"{name}: 해당 날짜 데이터 없음")

st.subheader("3. 한국 외국인·기관 수급")
st.write("KRX 또는 사용 권한이 있는 데이터 공급처에서 받은 CSV를 올리면 투자자별 누적 순매수와 최근 흐름을 요약합니다. 자동 수집은 공급처 접근 조건이 일정하지 않아 이 버전에서는 파일 업로드 방식입니다.")
st.caption("권장 열: date, investor, net_buy, market. 예: 2026-10-27, 외국인, 12500000000, 코스피현물. 현물과 선물은 반드시 구분하세요.")
flow_upload = st.file_uploader("투자자별 수급 CSV 업로드", type=["csv"], key="flow_csv")
flow_df = None
if flow_upload:
    flow_df, err = normalize_flow_csv(flow_upload)
    if err:
        st.error(err)
    elif flow_df is not None:
        flow_df = flow_df[flow_df["date"].dt.date <= selected_date]
        st.markdown("**업로드 자료 미리보기**")
        st.dataframe(flow_df.sort_values("date", ascending=False).head(40), use_container_width=True, hide_index=True)
        if not flow_df.empty:
            st.markdown("**시장·투자자별 누적 순매수 (업로드 자료 전체, 선택 날짜까지)**")
            summary = flow_df.groupby(["market", "investor"], as_index=False)["net_buy"].sum().sort_values("net_buy", ascending=False)
            st.dataframe(summary, use_container_width=True, hide_index=True)
            st.markdown("**최근 5개 날짜의 수급**")
            last_dates = sorted(flow_df["date"].dt.date.unique())[-5:]
            recent = flow_df[flow_df["date"].dt.date.isin(last_dates)].groupby([flow_df["date"].dt.strftime("%Y-%m-%d"), "market", "investor"], as_index=False)["net_buy"].sum()
            recent = recent.rename(columns={"date": "날짜"})
            st.dataframe(recent.sort_values("날짜", ascending=False), use_container_width=True, hide_index=True)
            st.info("수급은 시장별·상품별 단위가 같을 때만 비교하세요. 이 자료는 현재 자동 점수에 반영되지 않습니다.")
else:
    st.info("수급 CSV가 없으므로 수급 신호는 미평가 상태입니다. 수급 미확인을 긍정으로 처리하지 않습니다.")

st.subheader("4. FRED 미국 경제 데이터 (선택)")
st.write("FRED API 키가 있으면 CPI, 실업률, 연방기금금리, 10년물 금리, 비농업 고용, PCE 시계열을 조회합니다. 발표 예상치와 실제치의 자동 비교 기능은 별도 경제 캘린더 데이터 공급처가 필요합니다.")
with st.expander("FRED 데이터 조회 열기"):
    fred_key = st.text_input("FRED API Key (선택, 비밀번호 입력)", type="password")
    fred_start = st.date_input("FRED 시작 날짜", value=selected_date - timedelta(days=450), key="fred_start")
    if st.button("FRED 시계열 조회"):
        if not fred_key:
            st.warning("FRED API 키를 입력하세요.")
        else:
            try:
                import requests
                for title, (series_id, unit) in FRED_SERIES.items():
                    try:
                        df = load_fred_series(fred_key, series_id, fred_start, selected_date)
                        if df.empty:
                            st.caption(f"{title}: 조회 기간에 데이터 없음")
                        else:
                            st.markdown(f"**{title} ({series_id})**")
                            st.dataframe(df.tail(15), use_container_width=True, hide_index=True)
                    except Exception as e:
                        st.warning(f"{title} 조회 실패: {e}")
            except Exception as e:
                st.error(f"FRED 연결 실패: {e}")

st.subheader("5. 경제 이벤트 분석 기록")
st.write("아래 메모에 공식 발표의 실제치·시장 예상치·이전치와 발표 후 달러·금리·지수 반응을 입력해 기록할 수 있습니다.")
event_csv = st.file_uploader("경제 이벤트 CSV 업로드 (선택)", type=["csv"], key="event_csv")
if event_csv:
    try:
        event_df = pd.read_csv(event_csv)
        st.dataframe(event_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"이벤트 CSV 읽기 실패: {e}")
event_note = st.text_area("FOMC / CPI / 고용 / PCE 이벤트 메모", placeholder="이벤트 | 실제치 | 예상치 | 이전치 | 발표 후 달러 반응 | 미국 10년물 반응 | 한국 선물 반응", height=110)

st.subheader("6. 업종·대형주 위치 점검")
st.write("현재는 대표 대형주 차트를 제공하며, 자동 지지·저항·업종 breadth 계산은 다음 확장 단계입니다. 이동평균과 지지선은 차트에서 확인하고, 급등 추격 여부 및 손절 기준을 별도로 기록하세요.")
with st.expander("종목별 이동평균 참고"):
    ticker_name = st.selectbox("이동평균을 볼 종목", ["코스피 종합지수", "코스닥 종합지수", "삼성전자", "SK하이닉스", "현대차", "KB금융"])
    df = market_data.get(ticker_name, pd.DataFrame()).copy()
    if not df.empty and "Close" in df:
        df = df.loc[df.index.date <= selected_date]
        if not df.empty:
            df["MA20"] = df["Close"].rolling(20).mean()
            df["MA60"] = df["Close"].rolling(60).mean()
            st.line_chart(df[["Close", "MA20", "MA60"]], height=250)
            last = df.iloc[-1]
            st.write(f"최근 종가: **{fmt(last['Close'])}** · MA20: **{fmt(last['MA20'])}** · MA60: **{fmt(last['MA60'])}**")
        else:
            st.warning("선택 날짜까지 데이터가 없습니다.")
    else:
        st.warning("해당 종목 데이터를 가져오지 못했습니다.")

st.subheader("7. 매매 판단 요약")
valid = [r for r in rows if r["방향"] in ("상승", "하락", "횡보")]
up = sum(r["방향"] == "상승" for r in valid)
down = sum(r["방향"] == "하락" for r in valid)
flat = sum(r["방향"] == "횡보" for r in valid)
a, b, c = st.columns(3)
a.metric("상승", up); b.metric("하락", down); c.metric("횡보", flat)
st.markdown(f"""
- 분석 기준 날짜: **{selected_date}**
- 추세 기준: **최근 {bars}개 관측치**
- 시장 방향 점수: **{score if score is not None else '산출 불가'} / 100**
- 1차 판독: **{label}**
- 수급: **{'업로드 자료 있음(점수 미반영)' if flow_df is not None and not flow_df.empty else '미확인'}**
- 경제 이벤트: **{'메모/파일 입력됨' if event_note.strip() or event_csv else '미확인'}**
""")
st.warning("이 결과는 투자 판단 보조용 프로토타입입니다. 데이터 지연·누락, 거래시간 차이, 심볼 대체값에 유의하세요. 실제 주문 전 공식 데이터와 리스크 한도를 확인하세요.")
with st.expander("출처와 한계"):
    st.markdown("""
- 시장 시세: Yahoo Finance 공개 시세를 yfinance로 조회. 공식 실시간 체결 피드가 아니며 심볼이 작동하지 않을 수 있습니다.
- FRED: API 키로 거시경제 시계열 조회. CPI·고용 등은 관측 주기와 발표 시차가 있습니다.
- KRX 수급: CSV 업로드 방식. KRX 자동 연결은 포함하지 않습니다.
- VKOSPI: 공개 심볼 `^VKOSPI` 조회를 시도하지만 실패할 수 있으며, 실패하면 데이터 없음으로 표시합니다.
- 경제 캘린더의 실제치/예상치 자동 비교는 포함하지 않습니다.
- 점수는 백테스트되지 않은 휴리스틱이며 수익 확률이 아닙니다. 자동 주문 기능은 없습니다.
""")
