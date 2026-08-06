# 텔레그램 알림 설정 가이드

## 1. 텔레그램 봇 생성

### 1-1. BotFather로 봇 만들기
1. 텔레그램에서 **@BotFather** 검색 → 대화 시작
2. `/newbot` 입력
3. 봇 이름 입력 (예: `메리츠자동매매 알림`)
4. 봇 username 입력 (예: `meritz_trader_bot`) — 반드시 `_bot`으로 끝나야 함
5. 생성 완료 시 **Bot Token** 이 표시됨 (예: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

> ⚠️ Bot Token은 절대 외부에 노출하지 마세요.

---

## 2. Chat ID 확인

### 방법 A: 개인 채팅 Chat ID
1. 생성한 봇에게 아무 메시지 전송 (예: `/start`)
2. 브라우저에서 아래 URL 접속 (토큰 부분 교체):
   ```
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   ```
3. 응답 JSON에서 `"chat":{"id": 숫자}` 부분이 Chat ID

### 방법 B: 그룹 Chat ID
1. 봇을 그룹에 초대
2. 그룹에서 아무 메시지 전송
3. 위와 동일하게 `getUpdates` URL 접속
4. 그룹 Chat ID는 음수 (예: `-1001234567890`)

---

## 3. 구글 시트에 설정 입력

프로그램은 구글 시트의 첫 번째 시트에서 텔레그램 설정을 읽어옵니다.

| 셀 | 항목 | 입력 예시 |
|----|------|----------|
| E23 | Chat ID | `123456789` |
| E25 | Bot Token | `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` |

> config.json에 별도 설정 불필요 — 프로그램 시작 시 구글 시트에서 자동으로 읽어옵니다.

---

## 4. 알림 종류

프로그램이 자동으로 전송하는 알림:

| 알림 | 형식 | 발생 시점 |
|------|------|----------|
| 매매 체결 | `[매매 체결] 매수/매도 | 종목명 | 수량주 | 가격원 | 티어: N` | 주문 체결 시 |
| 오류 발생 | `[오류 발생] 에러 내용` | 프로그램 오류 시 |

---

## 5. 연결 테스트

브라우저 또는 터미널에서 직접 테스트:
```
https://api.telegram.org/bot<BOT_TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=테스트메시지
```

정상이면 텔레그램으로 "테스트메시지"가 도착합니다.

---

## 6. 문제 해결

| 증상 | 원인 및 해결 |
|------|-------------|
| `401 Unauthorized` | Bot Token이 잘못됨 → BotFather에서 토큰 재확인 |
| `400 Bad Request: chat not found` | Chat ID 오류 또는 봇에게 먼저 메시지를 보내지 않음 → 봇에게 `/start` 전송 후 재시도 |
| `403 Forbidden` | 봇이 그룹에서 제거됨 → 봇을 다시 그룹에 초대 |
| 알림이 안 옴 | 구글 시트 E23(chat_id), E25(bot_token) 셀이 비어있는지 확인 |
