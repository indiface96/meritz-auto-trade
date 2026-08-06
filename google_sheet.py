import gspread
import time
import logging
from oauth2client.service_account import ServiceAccountCredentials

_log = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def _retry_api(func, retries=3, delay=5):
    """구글 시트 API 호출 재시도 래퍼"""
    for attempt in range(1, retries + 1):
        try:
            return func()
        except gspread.exceptions.APIError as e:
            if attempt < retries:
                _log.warning(f"구글 시트 API 오류 ({attempt}/{retries}): {e}, {delay}초 후 재시도...")
                time.sleep(delay)
            else:
                raise
# 시트 내 고정 셀 위치 (행은 1-based, 컬럼은 알파벳)
CELL_MAP = {
    "hts_name":      "E4",
    "account_no":    "E6",
    "stock_code":    "E8",
    "investment":    "E10",
    "tier_total":    "E12",
    "tier1_usd":     "E14",
    "tier1_refresh": "E16",
    "buy_limit":     "E18",
    "last_update":   "K4",
    "current_tier":  "K6",
    "current_price": "K8",
    "balance":       "K10",
    "qty_diff":      "K12",
    "buy_count":     "K14",
    "sell_count":    "K16",
}


class GoogleSheetReader:
    def __init__(self, credentials_file, spreadsheet_id):
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, SCOPES)
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)
        self._ws_cache = {}  # 워크시트 객체 캐시
        self._data_cache = {}  # sheet_name -> (timestamp, target, tiers)
        self._cache_ttl = 30  # 캐시 유효시간(초)

    def _get_ws(self, sheet_name):
        """워크시트 객체를 캐싱하여 API 호출 절약"""
        if sheet_name not in self._ws_cache:
            self._ws_cache[sheet_name] = _retry_api(lambda: self.spreadsheet.worksheet(sheet_name))
        return self._ws_cache[sheet_name]

    def get_worksheet_names(self):
        return [ws.title for ws in self.spreadsheet.worksheets()]

    def get_target_and_tiers(self, sheet_name, max_tiers=50, force=False):
        """매매 대상 정보 + 티어 정보를 batch_get 1회로 읽는다. 캐시 TTL 적용."""
        if not force:
            cached = self._data_cache.get(sheet_name)
            if cached and (time.time() - cached[0]) < self._cache_ttl:
                return cached[1], cached[2]

        ws = self._get_ws(sheet_name)
        ranges = [f"E4:K18", f"V5:AC{5 + max_tiers}"]
        results = _retry_api(lambda: ws.batch_get(ranges))

        # 매매 대상 파싱
        all_data = results[0] if len(results) > 0 else []

        def get_cell(row_idx, col_offset):
            try:
                row = all_data[row_idx]
                return row[col_offset] if col_offset < len(row) else ""
            except (IndexError, TypeError):
                return ""

        stock_code = get_cell(4, 0)
        target = None
        if stock_code:
            target = {
                "sheet_name": sheet_name,
                "hts_name": get_cell(0, 0),
                "account_no": get_cell(2, 0),
                "stock_code": stock_code,
                "investment": _to_float(get_cell(6, 0)),
                "tier_total": _to_int(get_cell(8, 0)),
                "tier1_usd": _to_float(get_cell(10, 0)),
                "tier1_refresh": get_cell(12, 0).upper() == "TRUE",
                "buy_limit": _to_float(get_cell(14, 0)),
                "current_tier": _to_int(get_cell(2, 6)),
                "current_price": _to_float(get_cell(4, 6)),
                "balance": _to_int(get_cell(6, 6)),
                "qty_diff": _to_int(get_cell(8, 6)),
                "buy_count": _to_int(get_cell(10, 6)),
                "sell_count": _to_int(get_cell(12, 6)),
            }

        # 티어 파싱
        tier_rows = results[1] if len(results) > 1 else []
        tier_total = target["tier_total"] if target else 0
        tiers = []
        for row in tier_rows[:tier_total + 1]:
            if len(row) < 8:
                row.extend([""] * (8 - len(row)))
            tiers.append({
                "tier": _to_int(row[0]),
                "balance_qty": _to_int(row[1]),
                "buy_price": _to_float(row[4]),
                "buy_qty": _to_int(row[5]),
                "sell_price": _to_float(row[6]),
                "sell_qty": _to_int(row[7]),
            })

        self._data_cache[sheet_name] = (time.time(), target, tiers)
        return target, tiers

    def invalidate_cache(self, sheet_name=None):
        """캐시 무효화. sheet_name 지정 시 해당 시트만."""
        if sheet_name:
            self._data_cache.pop(sheet_name, None)
        else:
            self._data_cache.clear()

    def get_trade_targets(self, sheet_names):
        """지정된 시트들에서 매매 대상 정보를 읽는다."""
        targets = []
        for name in sheet_names:
            try:
                ws = self._get_ws(name)
                target = self._read_target(ws, name)
                if target:
                    targets.append(target)
            except gspread.exceptions.WorksheetNotFound:
                continue
        return targets

    def _read_target(self, ws, sheet_name):
        # E4:K18 한 번에 읽어서 API 1회로 줄임
        all_data = _retry_api(lambda: ws.get("E4:K18"))

        def get_cell(row_idx, col_offset):
            """row_idx: 0-based (E4=0), col_offset: 0=E, 6=K"""
            try:
                row = all_data[row_idx]
                return row[col_offset] if col_offset < len(row) else ""
            except (IndexError, TypeError):
                return ""

        stock_code = get_cell(4, 0)  # E8
        if not stock_code:
            return None

        return {
            "sheet_name": sheet_name,
            "hts_name": get_cell(0, 0),       # E4
            "account_no": get_cell(2, 0),     # E6
            "stock_code": stock_code,          # E8
            "investment": _to_float(get_cell(6, 0)),   # E10
            "tier_total": _to_int(get_cell(8, 0)),     # E12
            "tier1_usd": _to_float(get_cell(10, 0)),   # E14
            "tier1_refresh": get_cell(12, 0).upper() == "TRUE",  # E16
            "buy_limit": _to_float(get_cell(14, 0)),   # E18
            "current_tier": _to_int(get_cell(2, 6)),   # K6
            "current_price": _to_float(get_cell(4, 6)), # K8
            "balance": _to_int(get_cell(6, 6)),        # K10
            "qty_diff": _to_int(get_cell(8, 6)),       # K12
            "buy_count": _to_int(get_cell(10, 6)),     # K14
            "sell_count": _to_int(get_cell(12, 6)),    # K16
        }

    def get_all_tiers(self, sheet_name, tier_total):
        """모든 티어 정보를 한 번에 읽는다. (API 1회)"""
        ws = self._get_ws(sheet_name)
        start_row = 5
        end_row = 5 + tier_total
        rows = _retry_api(lambda: ws.get(f"V{start_row}:AC{end_row}"))
        tiers = []
        for row in rows:
            if len(row) < 8:
                row.extend([""] * (8 - len(row)))
            tiers.append({
                "tier": _to_int(row[0]),
                "balance_qty": _to_int(row[1]),
                "buy_price": _to_float(row[4]),
                "buy_qty": _to_int(row[5]),
                "sell_price": _to_float(row[6]),
                "sell_qty": _to_int(row[7]),
            })
        return tiers

    def get_tier_row(self, sheet_name, tier):
        """프로그램 영역에서 특정 티어의 매매 정보를 읽는다.
        프로그램 영역 헤더: 행4(0-based 행3), 티어 데이터는 행5(0-based 행4)부터
        컬럼: V=티어, W=잔고량, X=투자금, Y=티어평단, Z=매수(가), AA=매수(량), AB=매도(가), AC=매도(량)
        """
        ws = self._get_ws(sheet_name)
        # 프로그램 영역은 V열(22)부터, 행5(tier 0)부터 시작
        row = 5 + tier  # 1-based
        cells = ws.row_values(row)
        if len(cells) < 29:
            cells.extend([""] * (29 - len(cells)))
        return {
            "tier": _to_int(cells[21]),       # V
            "balance_qty": _to_int(cells[22]), # W
            "invest_amt": _to_float(cells[23]),# X
            "tier_avg": _to_float(cells[24]),  # Y
            "buy_price": _to_float(cells[25]), # Z
            "buy_qty": _to_int(cells[26]),     # AA
            "sell_price": _to_float(cells[27]),# AB
            "sell_qty": _to_int(cells[28]),    # AC
        }

    def update_cell(self, sheet_name, cell_addr, value):
        ws = self._get_ws(sheet_name)
        _retry_api(lambda: ws.update_acell(cell_addr, value))

    def batch_update_cells(self, sheet_name, updates):
        """{'셀주소': 값} 딕셔너리를 한 번의 API 호출로 업데이트"""
        if not updates:
            return
        ws = self._get_ws(sheet_name)
        batch = [{"range": addr, "values": [[val]]} for addr, val in updates.items()]
        _retry_api(lambda: ws.batch_update(batch))


def _to_float(val):
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _to_int(val):
    try:
        return int(float(str(val).replace(",", "")))
    except (ValueError, TypeError):
        return 0
