import logging
import logging.handlers
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from config import load_config
from meritz_hts import MeritzHTS
from google_sheet import GoogleSheetReader
from telegram_notify import TelegramNotifier

from datetime import datetime
from datetime import timedelta

_file_handler = logging.handlers.RotatingFileHandler(
    "trader.log", maxBytes=1_000_000, backupCount=1, encoding="utf-8"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[_file_handler, logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class AutoTrader:
    def __init__(self):
        self.cfg = load_config()
        now = datetime.now()
        self.start_datetime = now

        #문자열 형태의 시/분을 입력받아 목표 datetime 객체를 반환합니다.
        end_time_str = self.cfg.get("program_end_time", "15:40")
        end_h, end_m = map(int, end_time_str.split(":"))
        self.target_datetime = now.replace(
            hour=int(end_h), minute=int(end_m), second=0, microsecond=0
        )
        # 설정한 목표 시간이 현재 시간보다 이미 지난 시점이라면 '내일'로 설정
        if self.target_datetime <= now:
            self.target_datetime += timedelta(days=1)

        gs = self.cfg["google_sheet"]
        self.sheet = GoogleSheetReader(gs["credentials_file"], gs["spreadsheet_id"])
        self.hts = MeritzHTS(self.cfg.get("hts_path", ""), self.cfg.get("speed_multiplier", 1.0))
        self._hts_name = None  # 캐싱하여 반복 시트 읽기 방지
        self._prev_tier = {}  # {sheet_name: 이전 턴 현재 티어}
        self.notifier = self._init_telegram()

    def _init_telegram(self):
        sheet_configs = self.cfg.get("sheet_names", [])
        if not sheet_configs:
            return None
        first_name = sheet_configs[0]["name"] if isinstance(sheet_configs[0], dict) else sheet_configs[0]
        try:
            ws = self.sheet._get_ws(first_name)
            # batch_get 1회로 텔레그램 설정 로드 (기존 acell 2회 → 1회)
            results = ws.batch_get(["E23", "E25"])
            chat_id = results[0][0][0] if results[0] else None
            bot_token = results[1][0][0] if results[1] else None
            if bot_token and chat_id:
                logger.info("텔레그램 설정 로드 완료 (구글 시트)")
                return TelegramNotifier(bot_token, chat_id)
        except Exception as e:
            logger.error(f"텔레그램 설정 로드 실패: {e}")
        return None

    def _get_hts_name(self):
        """hts_name을 캐싱하여 반복 시트 읽기 방지"""
        if self._hts_name:
            return self._hts_name
        sheet_configs = self.cfg.get("sheet_names", [])
        ws_names = [s["name"] if isinstance(s, dict) else s for s in sheet_configs]
        targets = self.sheet.get_trade_targets(ws_names)
        self._hts_name = targets[0]["hts_name"] if targets else "iMeritz"
        return self._hts_name

    def login(self):
        hts_name = self._get_hts_name()

        if self.hts.is_logged_in(hts_name):
            logger.info(f"{hts_name} 창 발견, 로그인 스킵")
            return
        logger.info(f"{hts_name} 창 없음, iMeritz 실행...")
        self.hts.launch(hts_name)
        logger.info("iMeritz 실행 완료")

        account = self.cfg["accounts"][0]
        logger.info("로그인 시도...")
        self.hts.login(account["cert_password"], account.get("cert_index", 0))
        logger.info("로그인 완료")

    def _resize_main_window(self, hts_name):
        """메인 창을 1024x768로 리사이즈"""
        import ctypes
        from ctypes import wintypes
        hwnd = self.hts.find_hts_window(hts_name)
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.MoveWindow(hwnd, 0, 0, 1024, 768, True)
        logger.info("메인 창 1024x768 리사이즈 완료")

    def _ensure_hts_ready(self):
        """메인창 확인 → 없으면 재로그인(+리사이즈), 0060 없으면 재오픈(+최대화)"""
        hts_name = self._get_hts_name()

        hwnd = self.hts.find_hts_window(hts_name)
        if not hwnd:
            logger.warning(f"{hts_name} 창 없음, 재로그인 시도")
            if self.notifier:
                self.notifier.send(f"[복구] {hts_name} 창 유실, 재로그인 시도")
            self.login()
            hwnd = self.hts.find_hts_window(hts_name)
            if not hwnd:
                raise RuntimeError(f"재로그인 후에도 '{hts_name}' 창을 찾을 수 없습니다.")

        # HTS 초기화 대기 중 DLL 로드 에러 팝업 닫기
        self.hts._close_popups()

        self._resize_main_window(hts_name)

        # 0060 화면 확인 → 없으면 열기 + 최대화
        screen_hwnd = self.hts._find_screen_window(hwnd, "0060")
        if not screen_hwnd:
            logger.info("0060 화면 없음, 열기 시도")
            self.hts.open_screen_no_close(hwnd, "0060")
            self.hts._wait(1)
            screen_hwnd = self.hts._find_screen_window(hwnd, "0060")

        if screen_hwnd:
            logger.info("0060 화면 열림, 최대화")
            self.hts._maximize_screen(screen_hwnd)
        else:
            logger.info("0060 화면 없음")

        return hwnd

    def _execute_sheet(self, sheet_name):
        """개별 시트 매매 실행. 현재가가 매수/매도 범위 안이면 True, 밖이면 False 반환"""
        now = datetime.now()

        sheet_configs = self.cfg.get("sheet_names", [])
        # 해당 시트 설정 찾기
        end_time_str = "15:30"
        for sc in sheet_configs:
            if isinstance(sc, dict) and sc["name"] == sheet_name:
                end_time_str = sc.get("trade_end_time", "15:30")
                break
        end_h, end_m = map(int, end_time_str.split(":"))

        # 1. 종료 시각(end_datetime) 계산
        # 기본적으로 시작 날짜의 시:분으로 설정
        end_datetime = self.start_datetime.replace(
            hour=end_h, minute=end_m, second=0, microsecond=0
        )
        # 만약 시작 시각보다 종료 시각(시:분)이 더 작으면 익일 종료로 판단 (+1일)
        if (self.start_datetime.hour, self.start_datetime.minute) > (end_h, end_m):
            end_datetime += timedelta(days=1)

        # 2. 현재 시간과의 범위 비교 (now = datetime.now())
        # 시작 시각 이상이고, 최종 종료 시각 미만일 때만 매매 진행
        is_trading_time = self.start_datetime <= now < end_datetime

        # 3. 처리
        if not is_trading_time:
            # 이틀이 지나든, 종료 시간이 지났든 모두 여기서 걸러집니다.
            logger.info(f"{sheet_name} 매매 기간/시간 종료({self.start_datetime} ~ {end_datetime}), 스킵")
            return True

#        logger.info(f"{sheet_name}: start_t = {self.start_datetime} end_t = {end_datetime} is_trading_time = {is_trading_time}")

        try:
            self._ensure_hts_ready()
            self.sheet.invalidate_cache(sheet_name)
            t, tiers = self.sheet.get_target_and_tiers(sheet_name, force=True)
            if not t:
                logger.info(f"{sheet_name} 실행할 매매 대상 없음")
                return True
            self._process_target(t, tiers)
            # 현재가가 매수/매도 범위 안인지 판단
            return self._is_price_in_range(t, tiers)
        except Exception as e:
            logger.error(f"{sheet_name} 매매 실행 중 오류: {e}")
            if self.notifier:
                self.notifier.notify_error(f"{sheet_name} 매매 실행 중 오류: {e}")
            return True  # 오류 시 범위 내로 간주(느린 간격)



    def _is_price_in_range(self, t, tiers):
        """현재가가 현재 매칭 티어의 매수/매도 범위 안에 있으면 True"""
        price = getattr(self, '_last_current_price', 0)
        if price <= 0:
            return True
        matched = getattr(self, '_last_matched_info', None)
        if not matched:
            return True
        low = matched["buy_price"]
        high = matched["sell_price"]
        if low <= 0 or high <= 0:
            return True
        in_range = low <= price <= high
        logger.info(f"가격범위 체크: 현재가={price}, 현재티어 범위=[{low}, {high}], 범위내={in_range}")
        return in_range

    def _check_all_ended(self):
        all_ended = False

        now = datetime.now()
        if now >= self.target_datetime:
            all_ended = True

#        logger.info(f"Now={now}, Target={self.target_datetime}, all_ended = {all_ended}")
        return all_ended

    def _order_price(self, base_price, side):
        """test_only Y: 체결 안되게 20% 여유, N: 실제 가격 사용"""
        if self.cfg.get("test_only", "N") == "Y":
            return round(base_price * 0.8, 2) if side == "buy" else round(base_price * 1.2, 2)
        return base_price

    def _process_target(self, t, tiers):
        try:
            hts_name = t["hts_name"]
            stock_code = t["stock_code"]
            sheet_name = t["sheet_name"]
            account_no = t["account_no"]

            logger.info(f"{sheet_name} | 계좌:{account_no} | 종목:{stock_code}")

            hwnd = self.hts.find_hts_window(hts_name)
            if not hwnd:
                raise RuntimeError(f"'{hts_name}' 창을 찾을 수 없습니다.")

            # 매매 전 해당 종목 미체결 취소
            self.hts.cancel_all_0060(hwnd, stock_code=stock_code, account_no=account_no)

            # 현재가 + 잔고 조회 (0060 화면)
            current_price_str, balance_str = self.hts.get_price_qty_0060(hwnd, stock_code, account_no)

            # 조회 실패 시 매매 스킵
            if balance_str and int(balance_str) < 0:
                logger.warning(f"{stock_code} 가격/잔고 조회 실패(qty={balance_str}), 매매 스킵")
                if self.notifier:
                    self.notifier.send(f"[경고] {stock_code} 가격/잔고 조회 실패, 매매 스킵")
                return

            updates = {}
            balance = int(balance_str) if balance_str else 0
            current_price = float(current_price_str.replace(",", "")) if current_price_str else 0.0
            self._last_current_price = current_price

            # 잔고 읽기 실패 시 매매 스킵 (잘못된 티어 매칭 방지)
            if not balance_str and balance_str != "0":
                logger.warning(f"{stock_code} 잔고 읽기 실패, 매매 스킵")
                if self.notifier:
                    self.notifier.send(f"[경고] {stock_code} 잔고 읽기 실패, 매매 스킵")
                return

            if not current_price_str or current_price <= 0:
                logger.warning(f"{stock_code} 현재가 읽기 실패, 매매 스킵")
                if self.notifier:
                    self.notifier.send(f"[경고] {stock_code} 현재가 읽기 실패, 매매 스킵")
                return

            if tiers:
                matched_tier = 0
                matched_info = None
                for ti in tiers:
                    if ti["balance_qty"] <= balance:
                        matched_tier = ti["tier"]
                        matched_info = ti
                        if ti["balance_qty"] == balance:
                            break
                    else:
                        matched_tier = ti["tier"]
                        matched_info = ti
                        break

                updates["K6"] = str(matched_tier)
                self._last_matched_info = matched_info
                logger.info(f"{stock_code} 현재티어 {matched_tier} (잔고량 {balance})")

                # 티어 변화로 체결 횟수 판단
                prev_tier = self._prev_tier.get(sheet_name)
                if prev_tier is not None and prev_tier != matched_tier:
                    if matched_tier > prev_tier:
                        updates["K14"] = str(t.get("buy_count", 0) + (matched_tier - prev_tier))
                        logger.info(f"{stock_code} 티어 {prev_tier}->{matched_tier}, 매수 체결 K14 업데이트")
                    else:
                        updates["K16"] = str(t.get("sell_count", 0) + (prev_tier - matched_tier))
                        logger.info(f"{stock_code} 티어 {prev_tier}->{matched_tier}, 매도 체결 K16 업데이트")
                self._prev_tier[sheet_name] = matched_tier

                # 매매 방향 결정
                if matched_info and current_price > 0:
                    bp = matched_info["buy_price"]
                    sp = matched_info["sell_price"]
                    target_qty = matched_info["balance_qty"]
                    tier_idx = next((i for i, ti in enumerate(tiers) if ti["tier"] == matched_tier), -1)
                    signal = None  # "buy" / "sell" / None

                    logger.info(
                        f"{stock_code} 티어{matched_tier} 상세 | "
                        f"현재가:{current_price} | 매수가:{bp} | 매도가:{sp} | "
                        f"중간값:{(bp+sp)/2:.2f} | 목표잔고:{target_qty} | 현재잔고:{balance} | "
                        f"매수수량:{matched_info['buy_qty']} | 매도수량:{matched_info['sell_qty']}"
                    )

                    if matched_tier == 0:
                        if bp > 0 and current_price <= bp:
                            signal = "buy"
                        else:
                            logger.info(f"{stock_code} 0티어 매수 대기 (현재가{current_price} > 매수가{bp})")
                    elif matched_tier == tiers[-1]["tier"]:
                        # 마지막 티어: 매도만 시도
                        if sp > 0:
                            signal = "sell"
                            logger.info(f"{stock_code} 마지막 티어{matched_tier} 매도만 시도")
                    elif bp > 0 and sp > 0:
                        mid = (bp + sp) / 2
                        if current_price < mid:
                            signal = "buy"
                        elif current_price > mid:
                            signal = "sell"
                        else:
                            logger.info(f"{stock_code} 매매 대기 (현재가{current_price} == 중간{mid:.2f})")

                    # 1티어 갱신: 1티어 + 매도 조건 + 현재가 > 1티어USD + refresh=TRUE
                    if (signal == "sell" and matched_tier == 1
                            and t["tier1_refresh"] and current_price > t["tier1_usd"] > 0):
                        logger.info(
                            f"{stock_code} 1티어 갱신: 현재가({current_price}) > "
                            f"1티어USD({t['tier1_usd']}), 매도 스킵 후 재로드"
                        )
                        self.sheet.batch_update_cells(sheet_name, {"E14": current_price})
                        if self.notifier:
                            self.notifier.send(
                                f"[1티어 갱신] {stock_code} | "
                                f"1티어USD: {t['tier1_usd']} -> {current_price}"
                            )
                        # 매매 기준 재로드
                        _, tiers = self.sheet.get_target_and_tiers(sheet_name, force=True)
                        if not tiers:
                            logger.warning(f"{stock_code} 티어 재조회 실패, 매매 스킵")
                            return
                        # 재매칭
                        matched_tier = 0
                        matched_info = None
                        for ti in tiers:
                            if ti["balance_qty"] <= balance:
                                matched_tier = ti["tier"]
                                matched_info = ti
                                if ti["balance_qty"] == balance:
                                    break
                            else:
                                matched_tier = ti["tier"]
                                matched_info = ti
                                break
                        updates["K6"] = str(matched_tier)
                        logger.info(f"{stock_code} 1티어 갱신 후 재매칭 -> 티어{matched_tier}")
                        # 매도 스킵
                        signal = None

                    # 잔고 불일치 + 매매 신호 → 초과/부족분 반영
                    if balance != target_qty:
                        diff = balance - target_qty  # 양수=초과, 음수=부족
                        if signal == "sell" and matched_info["sell_qty"] > 0:
                            qty = matched_info["sell_qty"] + diff  # 매도량 + 초과분
                            if qty > 0:
                                msg = (f"[매도+잔고조정] {stock_code} (티어{matched_tier})\n"
                                       f"현재가: {current_price} | 잔고차이: {diff}주 | 시트매도량: {matched_info['sell_qty']}주\n"
                                       f"실제매도: {qty}주 | 매도가: {sp}")
                                logger.info(msg)
                                alert_sent, _ = self.hts.sell_0060(hwnd, stock_code, self._order_price(sp, "sell"), qty, account_no, telegram=self.notifier)
                                if self.notifier and not alert_sent:
                                    self.notifier.send(msg)
                        elif signal == "buy" and matched_info["buy_qty"] > 0:
                            qty = matched_info["buy_qty"] - diff
                            if qty > 0:
                                msg = (f"[매수+잔고조정] {stock_code} (티어{matched_tier})\n"
                                       f"현재가: {current_price} | 잔고차이: {diff}주 | 시트매수량: {matched_info['buy_qty']}주\n"
                                       f"실제매수: {qty}주 | 매수가: {bp}")
                                logger.info(msg)
                                alert_sent, _ = self.hts.buy_0060(hwnd, stock_code, self._order_price(bp, "buy"), qty, account_no, telegram=self.notifier)
                                if self.notifier and not alert_sent:
                                    self.notifier.send(msg)

                    # 잔고 일치 → 시트 매수/매도량으로 매매 주문
                    elif signal == "buy" and matched_info["buy_qty"] > 0:
                        qty = matched_info["buy_qty"]
                        msg = (f"[매수 주문] {stock_code} (티어{matched_tier})\n"
                               f"현재가: {current_price} | 매수가: {bp} | 수량: {qty}주")
                        logger.info(msg)
                        alert_sent, _ = self.hts.buy_0060(hwnd, stock_code, self._order_price(bp, "buy"), qty, account_no, telegram=self.notifier)
                        if self.notifier and not alert_sent:
                            self.notifier.send(msg)

                    elif signal == "sell" and matched_info["sell_qty"] > 0:
                        qty = matched_info["sell_qty"]
                        msg = (f"[매도 주문] {stock_code} (티어{matched_tier})\n"
                               f"현재가: {current_price} | 매도가: {sp} | 수량: {qty}주")
                        logger.info(msg)
                        alert_sent, _ = self.hts.sell_0060(hwnd, stock_code, self._order_price(sp, "sell"), qty, account_no, telegram=self.notifier)
                        if self.notifier and not alert_sent:
                            self.notifier.send(msg)

            if current_price_str:
                updates["K8"] = current_price_str
            if balance_str is not None:
                updates["K10"] = balance_str
            updates["K4"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if updates:
                self.sheet.batch_update_cells(sheet_name, updates)

            logger.info(f"{stock_code} 현재가:{current_price_str} 보유량:{balance_str}")

        except Exception as e:
            logger.error(f"종목 처리 오류 ({t.get('stock_code', '?')}): {e}")
            if self.notifier:
                self.notifier.notify_error(f"종목 처리 오류 ({t.get('stock_code', '?')}): {e}")

    def _handle_tier0(self, t, current_price):
        sheet_name = t["sheet_name"]
        stock_code = t["stock_code"]

        # 개별 update 2회 → batch 1회로 통합
        batch = {"K6": 1}
        if t["tier1_refresh"]:
            batch["E14"] = current_price
            logger.info(f"{stock_code} 1티어(USD) 갱신: {current_price}")

        self.sheet.batch_update_cells(sheet_name, batch)
        logger.info(f"0티어 매수: {stock_code} 티어 0->1")

    def run(self):
        self.login()
        sheet_configs = self.cfg.get("sheet_names", [])
        sheets = []
        for sc in sheet_configs:
            if isinstance(sc, dict):
                name = sc["name"]
                interval = sc.get("check_interval_minutes",
                                  self.cfg.get("check_interval_minutes", 5))
            else:
                name = sc
                interval = self.cfg.get("check_interval_minutes", 5)
            sheets.append({"name": name, "interval": interval})

        # 즉시 1회 실행 + 다음 실행 시각 설정
        for s in sheets:
            in_range = self._execute_sheet(s["name"])
            wait = s["interval"] * 60 if in_range else 5
            s["next_run"] = time.time() + wait
            logger.info(f"{s['name']}: {'범위내' if in_range else '범위밖'} → {wait}초 후 다음 실행")

        while True:
            time.sleep(wait)
            if self._check_all_ended():
                logger.info("모든 시트 매매 종료시간 경과, HTS 종료")
                self.hts.close_hts()
                sys.exit(0)
            now = time.time()
            for s in sheets:
                if now >= s["next_run"]:
                    in_range = self._execute_sheet(s["name"])
                    wait = s["interval"] * 60 if in_range else 5
                    s["next_run"] = now + wait
                    logger.info(f"{s['name']}: {'범위내' if in_range else '범위밖'} → {wait}초 후 다음 실행")
