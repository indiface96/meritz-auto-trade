# Google Sheet 설정 가이드

## 1. Google Cloud 프로젝트 및 서비스 계정 생성

### 1-1. Google Cloud Console 접속
1. https://console.cloud.google.com 접속
2. 새 프로젝트 생성 (또는 기존 프로젝트 선택)

### 1-2. Google Sheets API & Google Drive API 활성화
1. 좌측 메뉴 → **API 및 서비스** → **라이브러리**
2. "Google Sheets API" 검색 → **사용** 클릭
3. "Google Drive API" 검색 → **사용** 클릭

### 1-3. 서비스 계정 생성
1. 좌측 메뉴 → **API 및 서비스** → **사용자 인증 정보**
2. **+ 사용자 인증 정보 만들기** → **서비스 계정**
3. 서비스 계정 이름 입력 (예: `meritz-trader`) → 완료

### 1-4. credentials.json 다운로드
1. 생성된 서비스 계정 클릭
2. **키** 탭 → **키 추가** → **새 키 만들기** → JSON 선택
3. 다운로드된 JSON 파일을 `credentials.json`으로 이름 변경
4. 프로그램 폴더(`메리츠자동매매/`)에 복사

---

## 2. Google 스프레드시트 설정

### 2-1. 스프레드시트 공유
1. 사용할 Google 스프레드시트 열기
2. `credentials.json` 파일 내 `client_email` 값 확인 (예: `meritz-trader@프로젝트ID.iam.gserviceaccount.com`)
3. 스프레드시트 우측 상단 **공유** 클릭
4. 위 이메일 주소를 **편집자** 권한으로 추가

### 2-2. 스프레드시트 ID 확인
스프레드시트 URL에서 ID를 추출합니다:
```
https://docs.google.com/spreadsheets/d/[여기가_스프레드시트_ID]/edit
```

---

## 3. config.json 설정

```json
{
    "google_sheet": {
        "credentials_file": "credentials.json",
        "spreadsheet_id": "스프레드시트_ID"
    },
    "sheet_names": [
        {
            "name": "시트탭이름",
            "check_interval_minutes": 5,
            "trade_end_time": "07:30"
        }
    ]
}
```

| 항목 | 설명 |
|------|------|
| `credentials_file` | 서비스 계정 키 파일 경로 |
| `spreadsheet_id` | 스프레드시트 URL에서 추출한 ID |
| `sheet_names[].name` | 매매 대상 시트 탭 이름 |
| `check_interval_minutes` | 시트 조회 주기 (분) |
| `trade_end_time` | 매매 종료 시각 (HH:MM) |

---

## 4. 시트 구조 (셀 배치)

### 매매 대상 영역 (E열, K열)

| 셀 | 항목 | 설명 |
|----|------|------|
| E4 | HTS 이름 | 증권사 계정 이름 |
| E6 | 계좌번호 | 매매 계좌 |
| E8 | 종목코드 | 매매 대상 종목 |
| E10 | 투자금 | 총 투자금액 |
| E12 | 티어 총수 | 전체 티어 개수 |
| E14 | 1티어 USD | 1티어 기준 금액 |
| E16 | 1티어 갱신 | TRUE/FALSE |
| E18 | 매수 한도 | 매수 제한 금액 |
| K4 | 최종 업데이트 | 프로그램이 기록 |
| K6 | 현재 티어 | 프로그램이 기록 |
| K8 | 현재가 | 프로그램이 기록 |
| K10 | 잔고 | 프로그램이 기록 |
| K12 | 수량 차이 | 프로그램이 기록 |
| K14 | 매수 횟수 | 프로그램이 기록 |
| K16 | 매도 횟수 | 프로그램이 기록 |

### 티어 정보 영역 (V~AC열, 5행부터)

| 열 | 항목 |
|----|------|
| V | 티어 번호 |
| W | 잔고량 |
| X | 투자금 |
| Y | 티어 평단가 |
| Z | 매수가 |
| AA | 매수량 |
| AB | 매도가 |
| AC | 매도량 |

---

## 5. 문제 해결

| 증상 | 원인 및 해결 |
|------|-------------|
| `WorksheetNotFound` | `sheet_names`의 `name`이 실제 시트 탭 이름과 불일치 → 정확히 맞추기 |
| `APIError 403` | 서비스 계정에 스프레드시트 공유 안됨 → 편집자 권한 추가 |
| `APIError 429` | API 호출 한도 초과 → `check_interval_minutes` 값 늘리기 |
| `FileNotFoundError` | `credentials.json` 경로 오류 → 프로그램 폴더에 파일 존재 확인 |
