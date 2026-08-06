import logging
import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token, chat_id):
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id

    def send(self, message, retries=3):
        # 빠른 실행을 위해 결과를 보지 않고 return
        requests.post(self.api_url, data={"chat_id": self.chat_id, "text": message}, timeout=30)
        # for attempt in range(1, retries + 1):
        #     try:
        #         resp = requests.post(self.api_url, data={"chat_id": self.chat_id, "text": message}, timeout=30)
        #         if resp.ok:
        #             return
        #         logger.warning(f"텔레그램 전송 실패 ({attempt}/{retries}): {resp.status_code} {resp.text[:100]}")
        #     except Exception as e:
        #         logger.warning(f"텔레그램 전송 오류 ({attempt}/{retries}): {e}")
        #     if attempt < retries:
        #         import time
        #         time.sleep(5 * attempt)

    def notify_trade(self, trade_type, stock_name, quantity, price, tier):
        msg = f"[매매 체결] {trade_type} | {stock_name} | {quantity}주 | {price}원 | 티어: {tier}"
        self.send(msg)

    def notify_error(self, error_msg):
        msg = f"[오류 발생] {error_msg}"
        self.send(msg)
