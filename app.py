from datetime import date, timedelta
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Global Market Radar v2", page_icon="🌐", layout="wide")
st.title("🌐 Global Market Radar")
st.caption("v2 · 글로벌 시황 + 한국 수급 파일 분석 · 교육/연구용 · 자동 주문 없음")

ASSETS = {
    "나스닥 선물 (NQ)": "NQ=F", "다우 선물 (YM)": "YM=F",
    "독일 DAX 선물 (FDAX)": "FDAX=F", "중국 상하이종합 (현물 대리)": "000001.SS",
    "홍콩 항셍 (현물 대리)": "^HSI", "VIX": "^VIX",
    "달러인덱스 (DXY 대리)": "DX-Y.NYB", "원/달러 환율": "KRW=X",
    "WTI 원유 선물": "CL=F", "미국 10년물 금리 (^TNX)": "^TNX",
    "코스피 종합지수": "^KS11", "코스닥 종합지수": "^KQ11",
    "삼성전자": "005930.KS", "SK하이닉스": "000660.KS",
    "현대차": "005380.KS", "KB금융": "105560.KS",
}
GROUPS = {
    "글로벌 지수/선물": ["나스닥 선물 (NQ)", "다우 선물 (YM)", "독일 DAX 선물 (FDAX)", "중국 상하이종합 (현물 대리)", "홍콩 항셍 (현물 대리)"],
    "변동성": ["VIX"], "환율": ["달러인덱스 (DXY 대리)", "원/달러 환율"],
    "원자재·금리": ["WTI 원유 선물", "미국 10년물 금리 (^TNX)"],
    "한국 시장": ["코스피 종합지수", "코스닥 종합지수"],
    "대형주": ["삼성전자", "SK하이닉스", "현대차", "KB금융"],
}

def history(symbol, start, end, interval):
    try:
        df = yf.Ticker(symbol).history(start=start.isoformat(), end=end.isoformat(),
            interval=interval, auto_adjust=False, actions=False,
            prepost=(interval != "1d"), timeout=15)
        return df.dropna(subset=["Close"]) if df is not None and not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def pct(df, bars):
    if df.empty: return None
    s = pd.to_numeric(df["Close"], errors="coerce").dropna()
    if len(s) < 2: return None
    first, last = s.iloc[max(0, len(s)-bars-1)], s.iloc[-1]
    return None if pd.isna(first) or pd.isna(last) or first == 0 else float((last/first-1)*100)

def direction(v, threshold):
    if v is None or pd.isna(v): return "데이터 없음"
    if v >= threshold: return "상승"
    if v <= -threshold: return "하락"
    return "횡보"

def fmt(v):
    return "—" if v is None or pd.isna(v) else f"{v:,.2f}"

@st.cache_data(ttl=180, show_spinner=False)
def load_all(start_s, end_s, interval):
    return {n: history(s, date.fromisoformat(start_s), date.fromisoformat(end_s), interval) for n,s in ASSETS.items()}

with st.sidebar:
    st.header("분석 설정")
    selected_date = st.date_input("분석 기준 날짜", value=date.today(), max_value=date.today())
    mode = st.radio("분석 모드", ["과거 복기 / 장 마감", "장중 참고 (지연 가능)"])
    bars = st.selectbox("추세 비교 기준", [5, 20], format_func=lambda x: f"최근 {x}개 관측치")
    interval = "1d" if mode == "과거 복기 / 장 마감" else "5m"
    st.caption("무료 시세는 지연·누락될 수 있습니다. 공식 실시간 체결 피드가 아닙니다.")

start = selected_date - timedelta(days=max(60, bars*4)) if interval == "1d" else selected_date
end = selected_date + timedelta(days=1)
with st.spinner("시세를 조회하는 중..."):
    data = load_all(start.isoformat(), end.isoformat(), interval)

rows=[]
for name,symbol in ASSETS.items():
    df=data.get(name,pd.DataFrame())
    if not df.empty: df=df.loc[df.index.date <= selected_date]
    ch=pct(df,bars) if not df.empty else None
    last=float(df["Close"].iloc[-1]) if not df.empty else None
    th=.25 if ("VIX" in name or "금리" in name) else .5
    rows.append({"항목":name,"심볼":symbol,"최근값":last,"변화율(%)":ch,"방향":direction(ch,th),"관측시각":str(df.index[-1]) if not df.empty else "데이터 없음"})
byname={r["항목"]:r for r in rows}

# Transparent basic market score; oil and rates omitted because interpretation depends on cause.
signs={"나스닥 선물 (NQ)":1,"다우 선물 (YM)":1,"독일 DAX 선물 (FDAX)":1,
"중국 상하이종합 (현물 대리)":1,"홍콩 항셍 (현물 대리)":1,"VIX":-1,
"달러인덱스 (DXY 대리)":-1,"원/달러 환율":-1,"코스피 종합지수":1,"코스닥 종합지수":1}
weights={"나스닥 선물 (NQ)":1.3,"다우 선물 (YM)":1.0,"독일 DAX 선물 (FDAX)":.7,
"중국 상하이종합 (현물 대리)":.6,"홍콩 항셍 (현물 대리)":.7,"VIX":1.2,
"달러인덱스 (DXY 대리)":.8,"원/달러 환율":1.0,"코스피 종합지수":1.4,"코스닥 종합지수":.8}
ss=ws=0.0
for r in rows:
    n,t=r["항목"],r["방향"]
    if n in signs and t in ("상승","하락"):
        ss+=(1 if t=="상승" else -1)*signs[n]*weights[n]; ws+=weights[n]
score=round(max(0,min(100,(ss/ws+1)*50))) if ws else None
label="판단 불가" if score is None else "매수 우위 검토" if score>=70 else "선별 매수" if score>=55 else "중립·관망" if score>=40 else "방어 모드"

c1,c2,c3=st.columns(3)
c1.metric("종합 점수 (초기 규칙)",f"{score}/100" if score is not None else "—")
c2.metric("시장 모드",label)
c3.metric("시세 수집",f'{sum(r["변화율(%)"] is not None for r in rows)}/{len(rows)}')
st.caption("초기 점수는 검증된 예측 모델이 아닙니다. 경제지표와 한국 수급은 자동 반영되지 않으며 투자 권유가 아닙니다.")

st.subheader("1. 글로벌·매크로 대시보드")
for group,names in GROUPS.items():
    with st.expander(group, expanded=group in ["글로벌 지수/선물","변동성","한국 시장"]):
        tab=[]
        for n in names:
            r=byname[n]
            tab.append({"항목":n,"최근값":fmt(r["최근값"]),"최근 변화율":f'{fmt(r["변화율(%)"])}%' if r["변화율(%)"] is not None else "—","방향":r["방향"],"관측시각":r["관측시각"],"심볼":r["심볼"]})
        st.dataframe(pd.DataFrame(tab),use_container_width=True,hide_index=True)

st.subheader("2. 지수·대형주 차트")
selected=st.multiselect("차트 항목",list(ASSETS),default=["나스닥 선물 (NQ)","VIX","원/달러 환율","WTI 원유 선물","코스피 종합지수","삼성전자","SK하이닉스"])
for n in selected:
    df=data.get(n,pd.DataFrame())
    if not df.empty:
        df=df.loc[df.index.date <= selected_date]
        if not df.empty:
            st.markdown(f"**{n}** · {ASSETS[n]}")
            st.line_chart(df[["Close"]].rename(columns={"Close":n}),height=180)
    else: st.caption(f"{n}: 데이터 없음")

st.subheader("3. 한국 외국인·기관 수급 분석 (v2)")
st.write("KRX에서 내려받은 일별 투자자별 수급 CSV를 업로드하면 날짜별 외국인·기관 순매수 추세를 요약합니다. KRX 자동 API 연결은 아직 아니며, 파일의 열 이름이 데이터 제공처에 따라 다를 수 있습니다.")
st.markdown("**권장 CSV 형식 예시**: `date,investor,net_buy` — 날짜(YYYY-MM-DD), 투자자(외국인/기관), 순매수 금액(양수=순매수, 음수=순매도). 금액 단위는 업로드한 파일의 단위를 유지하세요.")
uploaded=st.file_uploader("수급 CSV 업로드",type=["csv"])
if uploaded:
    try:
        flow=pd.read_csv(uploaded)
        st.write("업로드된 열:",", ".join(map(str,flow.columns)))
        lower={str(c).strip().lower():c for c in flow.columns}
        date_col=next((lower[k] for k in ["date","날짜","일자","trading_date"] if k in lower),None)
        investor_col=next((lower[k] for k in ["investor","투자자","투자자구분","주체"] if k in lower),None)
        value_col=next((lower[k] for k in ["net_buy","순매수","순매수금액","순매수대금","순매수량"] if k in lower),None)
        if not (date_col and investor_col and value_col):
            st.error("자동 분석할 열을 찾지 못했어요. 열 이름을 date, investor, net_buy로 바꾼 CSV를 올려주세요.")
            st.dataframe(flow.head(20),use_container_width=True)
        else:
            flow=flow.rename(columns={date_col:"date",investor_col:"investor",value_col:"net_buy"})
            flow["date"]=pd.to_datetime(flow["date"],errors="coerce")
            flow["net_buy"]=pd.to_numeric(flow["net_buy"].astype(str).str.replace(",",""),errors="coerce")
            flow=flow.dropna(subset=["date","net_buy"])
            flow=flow[flow["date"].dt.date <= selected_date]
            flow["investor"]=flow["investor"].astype(str).str.strip()
            st.dataframe(flow.sort_values("date",ascending=False).head(30),use_container_width=True,hide_index=True)
            st.markdown("**투자자별 최근 누적 순매수**")
            summary=flow.groupby("investor",as_index=False)["net_buy"].sum().sort_values("net_buy",ascending=False)
            st.dataframe(summary,use_container_width=True,hide_index=True)
            st.markdown("**최근 5개 날짜의 투자자별 흐름**")
            last_dates=sorted(flow["date"].dt.date.unique())[-5:]
            recent=flow[flow["date"].dt.date.isin(last_dates)].groupby(["date","investor"],as_index=False)["net_buy"].sum()
            if not recent.empty:
                recent["date"]=recent["date"].dt.strftime("%Y-%m-%d")
                st.dataframe(recent.sort_values("date",ascending=False),use_container_width=True,hide_index=True)
            st.info("주의: CSV에 코스피 현물과 코스피200 선물 자료가 함께 있다면 시장 종류 열도 구분해야 합니다. 이 버전은 업로드한 행을 합산할 뿐 자동으로 시장별 분류하지 않습니다.")
    except Exception as e:
        st.error(f"CSV 읽기 실패: {e}")
else:
    st.info("수급 CSV를 업로드하면 분석 표가 여기에 표시됩니다. 수급 데이터가 없을 때는 매수 점수에 임의로 가산하지 않습니다.")

st.subheader("4. 경제지표·FOMC 메모")
st.text_area("이벤트 메모",placeholder="예: CPI 실제치 / 예상치 / 이전치, 고용지표, FOMC 발언, 발표 후 달러·금리 반응",height=100)
st.caption("FOMC·CPI·고용 예상치 대비 실제치 자동 비교, VKOSPI 자동 연결은 다음 개발 단계입니다.")

st.subheader("5. 방향 신호 요약")
valid=[r for r in rows if r["방향"] in ("상승","하락","횡보")]
a,b,c=st.columns(3)
a.metric("상승",sum(r["방향"]=="상승" for r in valid))
b.metric("하락",sum(r["방향"]=="하락" for r in valid))
c.metric("횡보",sum(r["방향"]=="횡보" for r in valid))
st.markdown(f"- 분석 날짜: **{selected_date}**\n- 비교 기준: **최근 {bars}개 관측치**\n- 1차 판독: **{label}**")
with st.expander("데이터 한계"):
    st.markdown("""
- Yahoo Finance 공개 시세는 공식 실시간 체결 피드가 아니며 지연·누락될 수 있습니다.
- 중국 항목은 현물 지수 대리값입니다.
- 수급 분석은 사용자가 업로드한 CSV에 대해서만 작동하며 KRX 자동 연결은 아닙니다.
- CSV의 단위와 의미가 정확한지 확인하세요. 현물·선물 순매수는 서로 합치지 않는 것이 좋습니다.
- 점수는 검증된 전략이 아니며 자동 주문 기능이 없습니다.
""")
