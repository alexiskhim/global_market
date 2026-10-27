# Global Market Radar — 첫 번째 실행 버전

아이폰 브라우저에서도 볼 수 있는 글로벌 시황 대시보드의 프로토타입입니다.
현재는 **시세 수집·방향 분류·간단한 규칙 점수·차트**를 제공합니다.
주문 제출 기능은 없습니다.

## 먼저 알아둘 점
- Yahoo Finance 공개 데이터는 공식 실시간 체결 피드가 아니며 지연·누락·심볼 오류가 발생할 수 있습니다.
- `FDAX=F`, `DX-Y.NYB`, `^VKOSPI` 등은 제공 상태가 바뀔 수 있습니다. 이 버전은 VKOSPI와 한국 외국인/기관 수급을 자동 연결하지 않습니다.
- 중국은 현물 지수 대리값을 사용하며, 요청한 중국 선물과 같지 않습니다.
- FOMC/CPI/고용의 예상치 대비 결과를 자동 분석하는 기능은 아직 없습니다. 이벤트 메모를 직접 입력하는 단계입니다.
- 초기 점수는 테스트용 휴리스틱일 뿐, 투자 조언이나 검증된 수익 전략이 아닙니다.

## A. 가장 쉬운 실행 방법: Streamlit Community Cloud
PC가 없어도 GitHub 저장소를 만들고 Streamlit Community Cloud에 배포하면 아이폰 Safari에서 접속할 수 있습니다.

1. GitHub 계정을 만들고 새 저장소를 만듭니다. 예: `global-market-radar`
2. 이 ZIP을 풀어 `app.py`, `requirements.txt`, `README.md`를 저장소 최상위에 업로드합니다.
3. `https://share.streamlit.io/`에 접속해 GitHub로 로그인합니다.
4. **Create app**을 선택합니다.
5. 저장소와 브랜치(보통 `main`)를 고르고 Main file path에 `app.py`를 입력합니다.
6. Deploy를 누릅니다. 빌드가 끝나면 `*.streamlit.app` 주소가 생깁니다.
7. 아이폰 Safari에서 그 주소를 열고 공유 버튼 → **홈 화면에 추가**를 선택하면 앱처럼 접근할 수 있습니다.

## B. 내 컴퓨터에서 실행하기
Python 3.11 또는 3.12를 설치한 뒤 프로젝트 폴더에서:

### macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Windows PowerShell
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

브라우저가 열리면 `http://localhost:8501`에서 볼 수 있습니다.
아이폰에서 로컬 PC 앱을 보려면 같은 Wi-Fi, 방화벽 및 네트워크 설정이 필요하므로 초보자에게는 Community Cloud 방식이 더 간단합니다.

## 폴더 구조
```text
global_market_radar/
├── app.py
├── requirements.txt
├── README.md
└── .streamlit/
    └── config.toml
```

## 데이터 소스 및 비용
- `yfinance`: 공개 Yahoo Finance 시세를 조회하는 오픈소스 라이브러리. Yahoo Finance와 제휴한 공식 제품이 아니며, 사용 목적 및 데이터 사용은 Yahoo 약관을 확인해야 합니다.
- Streamlit Community Cloud: 개인 프로젝트의 간단한 배포에 사용할 수 있는 무료 옵션이 있습니다. 서비스 조건과 리소스 한도는 바뀔 수 있습니다.
- FRED: 미국 거시경제 데이터 API. API 키가 필요합니다. 다음 단계에서 연결할 수 있습니다.
- KRX: 한국 지수와 투자자별 수급의 공식 출처. 상업적·실시간 데이터는 이용 조건이나 별도 비용이 적용될 수 있습니다.
- 예산: 이 첫 버전은 필수 유료 데이터 API 없이 시작하도록 설계했습니다. 월 1~3만 원 예산은 나중에 더 신뢰도 높은 시세·경제 캘린더를 추가할 때 사용하세요.

## 다음 개발 순서
1. KRX 외국인·기관 순매수 데이터 연결 및 데이터 출처/시간 표시
2. VKOSPI 연결
3. FRED API로 CPI, 실업률, 연방기금금리, 10년물 금리 기록 연결
4. 경제 캘린더의 실제치/예상치/이전치 및 발표시각 연결
5. 날짜별 데이터 스냅샷 저장(미래 데이터 누출 방지)
6. 점수 가중치 백테스트 및 매수/관망 기준 검증
7. 알림·자동 갱신은 그 뒤에 추가

## 안전
이 앱은 매매 결정을 보조하는 연구용 프로토타입입니다. 지연/누락 데이터를 바탕으로 자동 주문하지 마세요.
