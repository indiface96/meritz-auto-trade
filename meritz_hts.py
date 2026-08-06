import sys
import time
import ctypes
from ctypes import wintypes

import pyautogui
import pyperclip

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.15

user32 = ctypes.windll.user32

# 64bit 호환: 함수 시그니처 명시
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumChildWindows.restype = wintypes.BOOL
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_long
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_void_p]
user32.keybd_event.restype = None
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
user32.MoveWindow.restype = wintypes.BOOL
user32.BlockInput.argtypes = [wintypes.BOOL]
user32.BlockInput.restype = wintypes.BOOL

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

from contextlib import contextmanager


class MeritzHTS:
    def __init__(self, hts_path, speed_multiplier=1.0):
        from config import load_config
        self.hts_path = hts_path
        self.sm = max(speed_multiplier, 1.0)
        self.cfg = load_config()
        self._children_cache = {}  # hwnd -> (timestamp, children)
        self._cache_ttl = 0.5

    @contextmanager
    def _block_input(self):
        """자동화 구간 동안 사용자 마우스/키보드 입력 차단"""
        user32.BlockInput(True)
        try:
            yield
        finally:
            user32.BlockInput(False)

    def _wait(self, seconds):
        """성능 배수를 적용한 대기"""
        time.sleep(seconds * self.sm)

    def _wait_until(self, condition_fn, timeout=10, interval=0.2):
        """조건 충족 시 즉시 반환. timeout 초과 시 False 반환."""
        deadline = time.time() + timeout * self.sm
        while time.time() < deadline:
            result = condition_fn()
            if result:
                return result
            time.sleep(interval)
        return None

    def launch(self, hts_name="iMeritz"):
        import os
        import subprocess
        if self._find_window(hts_name, timeout=2):
            return
        hts_dir = os.path.dirname(self.hts_path) or None
        # 별도 프로세스로 HTS 실행 (EXE 환경변수 상속 방지)
        subprocess.Popen(
            f'start "" "{self.hts_path}"',
            shell=True, cwd=hts_dir
        )
        self._find_window("인증서 선택", timeout=60)

    def login(self, cert_password, cert_index=0):
        """인증서 선택 → 비밀번호 입력 → 확인"""
        import logging
        _log = logging.getLogger(__name__)
        _log.info("인증서 선택 대기...")

        cert_hwnd = self._find_window("인증서 선택", timeout=120)
        if not cert_hwnd:
            raise RuntimeError("인증서 선택 창을 찾을 수 없습니다.")

        with self._block_input():
            self._set_foreground(cert_hwnd)
            children = self._get_children(cert_hwnd, use_cache=False)

            # 인증서 목록 선택
            listview = self._find_child_by_class(children, "SysListView32")
            if not listview:
                raise RuntimeError("인증서 목록을 찾을 수 없습니다.")

            self._click_control(listview)
            self._wait(0.3)
            pyautogui.press("home")
            self._wait(0.1)
            for _ in range(cert_index):
                pyautogui.press("down")
                self._wait(0.05)
            self._wait(0.3)

            # 비밀번호 입력
            pw_edit = self._find_password_edit(children)
            if not pw_edit:
                raise RuntimeError("비밀번호 입력란을 찾을 수 없습니다.")
            self._click_control(pw_edit)
            self._wait(0.1)
            _type_text(cert_password)
            self._wait(0.1)

            # 확인 버튼
            confirm_btn = self._find_child_by_title(children, "확인")
            if confirm_btn:
                self._click_control(confirm_btn)
            else:
                pyautogui.press("enter")

        _log.info("인증서 확인 완료, 로그인 대기...")

        hts_hwnd = self._find_window("iMeritz", timeout=120)
        if not hts_hwnd:
            raise RuntimeError("로그인 후 HTS 메인 창을 찾을 수 없습니다.")
        _log.info("iMeritz was found!")

        # HTS 초기화 완료 대기: 화면번호 입력란이 나타나면 완료
        def _check_screen_edit():
            nonlocal hts_hwnd
            hts_hwnd = self.find_hts_window("iMeritz") or hts_hwnd
            self._set_foreground(hts_hwnd)
            children = self._get_children(hts_hwnd)
            edit = self._find_screen_edit(children)
            if not edit:
                self._close_popups()
            return edit

        result = self._wait_until(_check_screen_edit, timeout=60, interval=1.0)
        if result:
            _log.info(f"HTS 초기화 완료 screen_edit={result}")
        self._wait(3)

    def _get_children(self, parent, use_cache=False):
        if use_cache:
            cached = self._children_cache.get(parent)
            if cached and (time.time() - cached[0]) < self._cache_ttl:
                return cached[1]
        children = []
        def cb(hwnd, _):
            children.append(hwnd)
            return True
        user32.EnumChildWindows(parent, WNDENUMPROC(cb), 0)
        self._children_cache[parent] = (time.time(), children)
        return children

    def _find_child_by_class(self, children, class_name):
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == class_name:
                return hwnd
        return None

    def _find_password_edit(self, children):
        """비밀번호 입력 Edit (146px 크기)"""
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == "Edit":
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                if 140 <= w <= 300:
                    return hwnd
        return None

    def _find_child_by_title(self, children, title_keyword):
        for hwnd in children:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if title_keyword in buf.value:
                    return hwnd
        return None

    def _click_button(self, hwnd):
        """Button 컨트롤을 좌표 클릭한다."""
        self._click_control(hwnd)

    def _get_visible_buttons(self, parent):
        """부모 창 내 visible Button 핸들 목록 반환 (EnumChildWindows 순서)"""
        children = self._get_children(parent)
        buttons = []
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == "Button" and user32.IsWindowVisible(hwnd):
                buttons.append(hwnd)
        return buttons

    def _find_button_recursive(self, parent, title_keyword):
        """모든 자식 창을 재귀적으로 탐색하여 Button을 찾는다."""
        children = self._get_children(parent)
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == "Button":
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if title_keyword in buf.value:
                        return hwnd
        return None

    def _click_control(self, hwnd):
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2
        pyautogui.click(cx, cy)

    def find_hts_window(self, hts_name):
        """구글 시트의 HTS 창 이름으로 HTS 창을 찾는다. 크기가 가장 큰 창 우선."""
        candidates = []
        def cb(hwnd, _):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if hts_name in buf.value:
                    r = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(r))
                    w = r.right - r.left
                    h = r.bottom - r.top
                    candidates.append((hwnd, w * h))
            return True
        user32.EnumWindows(WNDENUMPROC(cb), 0)
        if not candidates and hts_name != "iMeritz":
            def cb2(hwnd, _):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if "iMeritz" in buf.value:
                        r = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(r))
                        w = r.right - r.left
                        h = r.bottom - r.top
                        candidates.append((hwnd, w * h))
                return True
            user32.EnumWindows(WNDENUMPROC(cb2), 0)
        if candidates:
            return max(candidates, key=lambda x: x[1])[0]
        return None

    def is_logged_in(self, hts_name="iMeritz"):
        return self._find_window(hts_name, timeout=3) is not None

    def close_hts(self):
        """HTS를 종료한다 (WM_CLOSE + 종료 확인 팝업 처리)."""
        import logging
        _log = logging.getLogger(__name__)
        hwnd = self.find_hts_window("iMeritz")
        if not hwnd:
            _log.info("[close_hts] iMeritz 창 없음")
            return
        user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        _log.info("[close_hts] WM_CLOSE 전송")
        self._wait(3)
        # 타이틀 없는 #32770 다이얼로그(종료 확인 팝업) 찾기
        popup = self._find_close_popup()
        if popup:
            btn = self._find_button_recursive(popup, "종료")
            if btn:
                self._click_control(btn)
                _log.info("[close_hts] 종료 버튼 클릭")
            else:
                pyautogui.press("enter")
        self._wait(2)

    def _find_close_popup(self, timeout=3):
        """타이틀 없는 #32770 다이얼로그(종료/취소 버튼 있는 창)를 찾는다."""
        for _ in range(timeout):
            result = [None]
            def _cb(h, _):
                if not user32.IsWindowVisible(h):
                    return True
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, cls, 256)
                if cls.value == "#32770" and user32.GetWindowTextLengthW(h) == 0:
                    result[0] = h
                    return False
                return True
            user32.EnumWindows(WNDENUMPROC(_cb), 0)
            if result[0]:
                return result[0]
            self._wait(1)
        return None

    # ── 2012 화면: 현재가 조회 ──
    # 화면번호 입력란의 HTS 창 기준 상대 좌표
    SCREEN_INPUT_REL_X = 44
    SCREEN_INPUT_REL_Y = 88

    def close_all_subwindows(self, hts_hwnd):
        """모든 서브창([xxxx] 타이틀)을 닫는다."""
        self._set_foreground(hts_hwnd)
        all_children = self._get_children(hts_hwnd)
        for hwnd in all_children:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value.startswith("[") and "]" in buf.value:
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        self._wait(1)

    def _set_edit_text(self, hwnd, text):
        """Edit 컨트롤에 텍스트를 직접 설정한다."""
        WM_SETTEXT = 0x000C
        buf = ctypes.create_unicode_buffer(text)
        user32.SendMessageW(hwnd, WM_SETTEXT, 0, ctypes.addressof(buf))

    def _find_screen_edit(self, children):
        """화면번호 입력란 Edit를 찾는다. 메리츠(47x15) 우선, 키움(39x12) 펴백."""
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == "Edit":
                r = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                w = r.right - r.left
                h = r.bottom - r.top
                if 45 <= w <= 50 and 13 <= h <= 17:
                    return hwnd
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == "Edit":
                r = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                w = r.right - r.left
                h = r.bottom - r.top
                if w == 39 and h == 12:
                    return hwnd
        return None

    def _input_screen_no(self, screen_edit, screen_no):
        """화면번호 입력란에 화면번호를 입력한다 (Home+Del+Backspace로 지우고 타이핑)."""
        self._click_control(screen_edit)
        self._wait(0.3)
        pyautogui.press("home")
        for _ in range(6):
            pyautogui.press("delete")
            self._wait(0.05)
        pyautogui.press("end")
        for _ in range(6):
            pyautogui.press("backspace")
            self._wait(0.05)
        pyautogui.typewrite(screen_no, interval=0.05)
        self._wait(0.3)
        pyautogui.press("enter")

    def open_screen_no_close(self, hts_hwnd, screen_no):
        """기존 서브창을 닫지 않고 화면번호를 열다. DLL 로딩 지연 대응 재시도."""
        for attempt in range(3):
            self._set_foreground(hts_hwnd)
            children = self._get_children(hts_hwnd)
            screen_edit = self._find_screen_edit(children)
            if screen_edit:
                self._input_screen_no(screen_edit, screen_no)
                self._wait(0.5)
                self._close_popups()
                # 화면이 열릴 때까지 대기
                self._wait_until(
                    lambda: self._find_screen_window(hts_hwnd, screen_no),
                    timeout=5, interval=0.3
                )
                return
            self._wait(3)
        raise RuntimeError("화면번호 입력란을 찾을 수 없습니다.")

    def open_screen(self, hts_hwnd, screen_no):
        """화면번호 입력란에 화면번호를 입력하여 화면을 연다."""
        self.close_all_subwindows(hts_hwnd)
        self._set_foreground(hts_hwnd)

        children = self._get_children(hts_hwnd)
        screen_edit = self._find_screen_edit(children)
        if not screen_edit:
            raise RuntimeError("화면번호 입력란을 찾을 수 없습니다.")

        self._input_screen_no(screen_edit, screen_no)
        self._wait(0.5)

    def _find_screen_window(self, hts_hwnd, screen_no):
        """화면번호로 서브창을 찾는다. [2302] 또는 [02302] 형식 모두 대응."""
        all_children = self._get_children(hts_hwnd)
        for tag in [f"[{screen_no}]", f"[0{screen_no}]"]:
            hwnd = self._find_child_by_title(all_children, tag)
            if hwnd:
                return hwnd
        return None

    def open_screen_with_retry(self, hts_hwnd, screen_no, max_retries=2):
        """화면을 열고 실제로 열렸는지 확인. 못 찾으면 재시도."""
        import logging
        _log = logging.getLogger(__name__)
        for attempt in range(1, max_retries + 1):
            self._close_popups()
            self.open_screen(hts_hwnd, screen_no)
            screen_hwnd = self._find_screen_window(hts_hwnd, screen_no)
            if screen_hwnd:
                return screen_hwnd
            _log.warning(f"[{screen_no}] 화면 못 찾음 ({attempt}/{max_retries}), 재시도...")
            self._wait(1)
        raise RuntimeError(f"[{screen_no}] 화면을 찾을 수 없습니다.")

    def _set_foreground(self, hwnd):
        """foreground 강제 전환"""
        if user32.GetForegroundWindow() == hwnd:
            return
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.keybd_event(0x12, 0, 0, None)   # Alt down
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(0x12, 0, 2, None)   # Alt up
        self._wait(0.3)

    @staticmethod
    def _normalize_account(acct):
        """\"60153681\" → \"6015-3681\" 형식으로 통일"""
        acct = acct.replace("-", "")
        if len(acct) == 8:
            return acct[:4] + "-" + acct[4:]
        return acct

    def _select_account(self, screen_hwnd, account_no, max_retries=2):
        """화면의 계좌번호 Edit 클릭 → 드롭다운 ListView에서 계좌 선택 (재시도 포함)"""
        import logging
        _log = logging.getLogger(__name__)
        for attempt in range(1, max_retries + 1):
            try:
                return self._select_account_inner(screen_hwnd, account_no)
            except RuntimeError as e:
                if attempt < max_retries:
                    _log.warning(f"계좌 선택 실패 ({attempt}/{max_retries}): {e}, 재시도...")
                    self._wait(1)
                else:
                    raise

    def _select_account_inner(self, screen_hwnd, account_no):
        """계좌 선택 내부 로직"""
        children = self._get_children(screen_hwnd)
        acct_edit = None
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == "Edit":
                r = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                w = r.right - r.left
                h = r.bottom - r.top
                if 60 <= w <= 125 and h == 16:
                    txt = self._read_edit_text(hwnd)
                    if "-" in txt or txt.isdigit():
                        acct_edit = hwnd
                        break
        if not acct_edit:
            raise RuntimeError("계좌번호 입력란을 찾을 수 없습니다.")

        import logging
        _log = logging.getLogger(__name__)
        target = self._normalize_account(account_no)

        # 현재 계좌가 이미 일치하면 스킵
        cur = self._normalize_account(self._read_edit_text(acct_edit))
        er = wintypes.RECT()
        user32.GetWindowRect(acct_edit, ctypes.byref(er))
        _log.info(f"계좌 Edit='{cur}' target='{target}' pos=({er.left},{er.top},{er.right},{er.bottom})")
        if target in cur:
            return

        er = wintypes.RECT()
        user32.GetWindowRect(acct_edit, ctypes.byref(er))

        # Edit 클릭 → 드롭다운 열기 → 항목 수 확인
        self._click_control(acct_edit)
        self._wait(1)
        pt = wintypes.POINT(er.left + 60, er.bottom + 5)
        lv = user32.WindowFromPoint(pt)
        lv_rect = wintypes.RECT()
        user32.GetWindowRect(lv, ctypes.byref(lv_rect))
        LVM_GETITEMCOUNT = 0x1004
        count = ctypes.c_long(user32.SendMessageW(lv, LVM_GETITEMCOUNT, 0, 0)).value
        lv_cx = (lv_rect.left + lv_rect.right) // 2
        _log.info(f"드롭다운 count={count}")

        # 첫 항목 클릭으로 드롭다운 닫기
        pyautogui.click(lv_cx, lv_rect.top + 7)
        self._wait(1)
        txt = self._normalize_account(self._read_edit_text(acct_edit))
        _log.info(f"계좌 드롭다운 [0] '{txt}' (target='{target}')")
        if target in txt:
            return

        for i in range(1, count):
            self._click_control(acct_edit)
            self._wait(1)
            lv = user32.WindowFromPoint(pt)
            lv_rect2 = wintypes.RECT()
            user32.GetWindowRect(lv, ctypes.byref(lv_rect2))
            item_y = lv_rect2.top + 7 + i * 13
            pyautogui.click(lv_cx, item_y)
            self._wait(1)
            txt = self._normalize_account(self._read_edit_text(acct_edit))
            _log.info(f"계좌 드롭다운 [{i}] '{txt}' (target='{target}')")
            if target in txt:
                return

        self._wait(1)
        raise RuntimeError(f"계좌번호 '{account_no}'를 찾을 수 없습니다.")

    def get_price_qty_0060(self, hts_hwnd, stock_code, account_no=None):
        """보유종목 탭에서 종목코드 일치하는 행의 현재가 + 보유수량 읽기"""
        import logging
        _log = logging.getLogger(__name__)
        with self._block_input():
            return self._get_price_qty_0060_inner(hts_hwnd, stock_code, account_no)

    def _get_price_qty_0060_inner(self, hts_hwnd, stock_code, account_no=None):
        import logging
        _log = logging.getLogger(__name__)
        self._set_foreground(hts_hwnd)

        # 1) 0060 화면 열기
        screen_hwnd = self._find_screen_window(hts_hwnd, "0060")
        if not screen_hwnd:
            self.open_screen_no_close(hts_hwnd, "0060")
            screen_hwnd = self._find_screen_window(hts_hwnd, "0060")
        if not screen_hwnd:
            raise RuntimeError("0060 화면을 찾을 수 없습니다.")

        self._maximize_screen(screen_hwnd)
        sr = wintypes.RECT()
        user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))

        # 2) 계좌 위치 파악 + 비밀번호
        children = self._get_children(screen_hwnd)
        acct_btn = self._find_acct_btn(children, sr)
        acct_y = 0
        if acct_btn:
            ar = wintypes.RECT()
            user32.GetWindowRect(acct_btn, ctypes.byref(ar))
            acct_y = ar.top - sr.top

        self._input_account_password(screen_hwnd, acct_y)

        # 3) 하단 오른쪽 탭 → 보유종목 탭 클릭 (offset=425)
        children = self._get_children(screen_hwnd)
        user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
        bottom_tab = self._find_bottom_right_tab(children, sr)
        if not bottom_tab:
            _log.warning(f"[get_price_qty] {stock_code} 하단 탭 못찾음, skip")
            return "", "-1"
        btr = wintypes.RECT()
        user32.GetWindowRect(bottom_tab, ctypes.byref(btr))
        pyautogui.click(btr.left + 425, btr.top + 12)
        self._wait(1)

        # 4) 그리드 행 클릭하며 MaskEdit에서 종목 찾기
        children = self._get_children(screen_hwnd)
        user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
        tab_ry = btr.top - sr.top
        grid_hwnd = self._find_grid(children, sr, tab_ry)
        if not grid_hwnd:
            _log.warning(f"[get_price_qty] {stock_code} 그리드 못찾음, skip")
            return "", "-1"

        gr = wintypes.RECT()
        user32.GetWindowRect(grid_hwnd, ctypes.byref(gr))
        row_height = 20
        header_height = 20
        max_rows = (gr.bottom - gr.top - header_height) // row_height
        prev_text = ""

        for i in range(max_rows):
            row_y = gr.top + header_height + i * row_height + row_height // 2
            pyautogui.click(gr.left + 100, row_y)
            self._wait(0.5)
            children2 = self._get_children(screen_hwnd)
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            found_data = False
            for h in children2:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, cls, 256)
                if cls.value == "iMeritz MaskEdit":
                    text = self._read_edit_text(h)
                    if text and "주식잔고" in text:
                        found_data = True
                        if i > 0 and text == prev_text:
                            found_data = False
                            break
                        prev_text = text
                        parts = text.split("|")
                        if len(parts) >= 10 and parts[3].upper() == stock_code.upper():
                            price_str = parts[8]
                            qty_str = parts[9]
                            _log.info(f"[get_price_qty] {stock_code} price={price_str} qty={qty_str}")
                            return price_str, qty_str
                        break
            if not found_data:
                break

        # 보유종목에서 못 찾으면 한번 더 시도
        _log.info(f"[get_price_qty] {stock_code} 보유종목 1차 탐색 실패, 재시도")
        pyautogui.click(btr.left + 425, btr.top + 12)
        self._wait(1)
        children = self._get_children(screen_hwnd)
        user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
        grid_hwnd = self._find_grid(children, sr, btr.top - sr.top)
        if grid_hwnd:
            user32.GetWindowRect(grid_hwnd, ctypes.byref(gr))
            max_rows = (gr.bottom - gr.top - header_height) // row_height
            prev_text = ""
            for i in range(max_rows):
                row_y = gr.top + header_height + i * row_height + row_height // 2
                pyautogui.click(gr.left + 100, row_y)
                self._wait(0.5)
                children2 = self._get_children(screen_hwnd)
                user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
                found_data = False
                for h in children2:
                    cls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(h, cls, 256)
                    if cls.value == "iMeritz MaskEdit":
                        text = self._read_edit_text(h)
                        if text and "주식잔고" in text:
                            found_data = True
                            if i > 0 and text == prev_text:
                                found_data = False
                                break
                            prev_text = text
                            parts = text.split("|")
                            if len(parts) >= 10 and parts[3].upper() == stock_code.upper():
                                price_str = parts[8]
                                qty_str = parts[9]
                                _log.info(f"[get_price_qty] {stock_code} price={price_str} qty={qty_str} (재시도)")
                                return price_str, qty_str
                            break
                if not found_data:
                    break

        # 보유종목에 없으면 매도 탭에서 현재가만 읽기 (잔고=0)
        _log.info(f"[get_price_qty] {stock_code} 보유종목에 없음, 매도탭에서 현재가 조회")
        children = self._get_children(screen_hwnd)
        user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
        tab_ctrl = self._find_left_tab(children, sr, acct_y)
        if tab_ctrl:
            tr = wintypes.RECT()
            user32.GetWindowRect(tab_ctrl, ctypes.byref(tr))
            pyautogui.click(tr.left + 45, tr.top + 12)  # 매도 탭
            self._wait(1)

        # 종목코드 입력
        children = self._get_children(screen_hwnd)
        user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
        tab_y = 0
        if tab_ctrl:
            tr2 = wintypes.RECT()
            user32.GetWindowRect(tab_ctrl, ctypes.byref(tr2))
            tab_y = tr2.top - sr.top
        code_edit = None
        for h in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, cls, 256)
            if cls.value == "iMeritz MaskEdit2":
                r = wintypes.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                rx = r.left - sr.left
                ry = r.top - sr.top
                w = r.right - r.left
                if 73 <= w <= 100 and 30 <= rx <= 50 and tab_y < ry < tab_y + 50:
                    code_edit = h
                    break
        if code_edit:
            current_code = self._read_edit_text(code_edit).strip().upper()
            if current_code != stock_code.upper():
                r = wintypes.RECT()
                user32.GetWindowRect(code_edit, ctypes.byref(r))
                cx = (r.left + r.right) // 2
                cy = (r.top + r.bottom) // 2
                pyautogui.doubleClick(cx, cy)
                self._wait(0.3)
                pyautogui.typewrite(stock_code, interval=0.05)
                self._wait(0.3)
                pyautogui.press("enter")
                self._wait(3)

        # 현재가 읽기 - 매도탭 가격란 (code_y + 94 위치)
        self._wait(1)
        children = self._get_children(screen_hwnd)
        user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
        code_y = 0
        if code_edit:
            cr = wintypes.RECT()
            user32.GetWindowRect(code_edit, ctypes.byref(cr))
            code_y = cr.top - sr.top
        if code_y:
            # 1차: 기존 좌표로 시도 (tolerance 확대)
            for offset in [94, 88, 100, 80, 110]:
                price_ctrl = self._find_maskedit_by_rel(children, sr, 39, code_y + offset, 76, tolerance=15)
                if price_ctrl:
                    price_str = self._read_edit_text(price_ctrl)
                    if price_str and any(c.isdigit() for c in price_str):
                        _log.info(f"[get_price_qty] {stock_code} price={price_str} qty=0 (매도탭, offset={offset})")
                        return price_str, "0"
            # 2차: code_edit 아래 영역의 MaskEdit 중 숫자가 있는 것 탐색
            _log.info(f"[get_price_qty] {stock_code} 가격란 좌표 탐색 시작 (code_y={code_y})")
            for h in children:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, cls, 256)
                if cls.value == "iMeritz MaskEdit":
                    r = wintypes.RECT()
                    user32.GetWindowRect(h, ctypes.byref(r))
                    rx = r.left - sr.left
                    ry = r.top - sr.top
                    w = r.right - r.left
                    if rx < 150 and code_y + 50 < ry < code_y + 150 and 50 <= w <= 100:
                        text = self._read_edit_text(h)
                        _log.info(f"  MaskEdit rx={rx} ry={ry} w={w} text='{text}'")
                        if text and any(c.isdigit() for c in text) and "|" not in text:
                            _log.info(f"[get_price_qty] {stock_code} price={text} qty=0 (폴백)")
                            return text, "0"

        _log.warning(f"[get_price_qty] {stock_code} 현재가 조회 실패, skip")
        return "", "-1"

    def _input_account_password(self, screen_hwnd, acct_y, max_retries=3):
        """0060 비밀번호 입력. 창을 새로 열었을 때 컨트롤 로딩 지연 대응을 위해 재시도."""
        import logging
        _log = logging.getLogger(__name__)
        acct_pw = self.cfg.get("accounts", [{}])[0].get("account_password", "")
        if not acct_pw or not acct_y:
            return
        WM_GETTEXTLENGTH = 0x000E
        for attempt in range(max_retries):
            children = self._get_children(screen_hwnd)
            sr = wintypes.RECT()
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            pw_edit = self._find_maskedit_by_rel(children, sr, 217, acct_y, 33, tolerance=12)
            if pw_edit:
                # 이미 입력되어 있으면 스킵
                cur_len = ctypes.c_long(user32.SendMessageW(pw_edit, WM_GETTEXTLENGTH, 0, 0)).value
                if cur_len == len(acct_pw):
                    _log.info(f"비밀번호 이미 입력됨 (len={cur_len})")
                    return
                self._click_control(pw_edit)
                self._wait(0.5)
                pyautogui.hotkey("ctrl", "a")
                self._wait(0.2)
                pyautogui.press("delete")
                self._wait(0.2)
                _type_text(acct_pw)
                self._wait(0.5)
                # 입력 확인
                pw_len = ctypes.c_long(user32.SendMessageW(pw_edit, WM_GETTEXTLENGTH, 0, 0)).value
                if pw_len == len(acct_pw):
                    _log.info(f"비밀번호 입력 확인 (len={pw_len})")
                    pyautogui.press("tab")
                    self._wait(0.5)
                    return
                _log.warning(f"비밀번호 입력 실패 (len={pw_len}, 기대={len(acct_pw)}), 재시도 ({attempt+1}/{max_retries})")
                self._wait(1)
                continue
            self._wait(1)

    def _find_maskedit_by_rel(self, children, sr, rel_x, rel_y, width, tolerance=5):
        """iMeritz MaskEdit를 상대좌표+너비로 찾는다. 숫자 데이터가 있는 것 우선."""
        candidates = []
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value != "iMeritz MaskEdit":
                continue
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            rx = r.left - sr.left
            ry = r.top - sr.top
            w = r.right - r.left
            if abs(rx - rel_x) <= tolerance and abs(ry - rel_y) <= tolerance and abs(w - width) <= tolerance:
                candidates.append(hwnd)
        # 숫자가 있는 컨트롤 우선
        for hwnd in candidates:
            text = self._read_edit_text(hwnd)
            if text and any(c.isdigit() for c in text):
                return hwnd
        return candidates[0] if candidates else None

    def _find_maskedit2_by_rel(self, children, sr, rel_x, rel_y, width, tolerance=5):
        """iMeritz MaskEdit2를 상대좌표+너비로 찾는다."""
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value != "iMeritz MaskEdit2":
                continue
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            rx = r.left - sr.left
            ry = r.top - sr.top
            w = r.right - r.left
            if abs(rx - rel_x) <= tolerance and abs(ry - rel_y) <= tolerance and abs(w - width) <= tolerance:
                return hwnd
        return None

    def _find_button_by_rel_size(self, children, sr, rel_x, rel_y, width, height, tolerance=5):
        """Button을 상대좌표+크기로 찾는다."""
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value != "Button":
                continue
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            rx = r.left - sr.left
            ry = r.top - sr.top
            w = r.right - r.left
            h = r.bottom - r.top
            if abs(rx - rel_x) <= tolerance and abs(ry - rel_y) <= tolerance and abs(w - width) <= tolerance and abs(h - height) <= tolerance:
                return hwnd
        return None

    def _find_acct_btn(self, children, sr):
        """계좌 선택 버튼을 찾는다. (rx~85-115, w~100-220, ry>15)
        상단 타이틀 영역(ry<15) 제외, 마지막 매칭 우선 (아래쪽 계좌 버튼)"""
        found = None
        for h in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, cls, 256)
            if cls.value == "Button":
                r = wintypes.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                rx = r.left - sr.left
                ry = r.top - sr.top
                w = r.right - r.left
                if 85 <= rx <= 115 and 100 <= w <= 220 and ry > 15:
                    found = h
        return found

    def _find_bottom_right_tab(self, children, sr):
        """하단 오른쪽 SysTabControl32를 찾는다. (rx>290, ry>270, w>600)"""
        for h in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, cls, 256)
            if cls.value == "SysTabControl32":
                r = wintypes.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                rx = r.left - sr.left
                ry = r.top - sr.top
                w = r.right - r.left
                if rx > 290 and ry > 270 and w > 600:
                    return h
        return None

    def _find_left_tab(self, children, sr, acct_y=0):
        """왼쪽 매수/매도 SysTabControl32를 찾는다. (rx<15, w~300-400, h>100)"""
        for h in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, cls, 256)
            if cls.value == "SysTabControl32":
                r = wintypes.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                rx = r.left - sr.left
                ry = r.top - sr.top
                w = r.right - r.left
                ht = r.bottom - r.top
                if rx < 15 and 300 <= w <= 400 and ht > 100 and ry > acct_y:
                    return h
        return None

    def _find_grid(self, children, sr, tab_ry):
        """GXWND 그리드를 찾는다. (ry>tab_ry, rx>290, w>400)"""
        for h in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, cls, 256)
            if cls.value == "GXWND":
                r = wintypes.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                ry = r.top - sr.top
                rx = r.left - sr.left
                w = r.right - r.left
                if ry > tab_ry and rx > 290 and w > 400:
                    return h
        return None

    def _maximize_screen(self, screen_hwnd):
        """서브창을 최대화한다. 이미 최대화면 스킵."""
        import ctypes as _ct
        wp = _ct.create_string_buffer(44)
        _ct.windll.user32.GetWindowPlacement(screen_hwnd, _ct.byref(wp))
        show_cmd = int.from_bytes(wp[8:12], 'little')
        if show_cmd == 3:  # SW_SHOWMAXIMIZED
            return
        user32.ShowWindow(screen_hwnd, 3)  # SW_MAXIMIZE
        self._wait(0.3)

    def buy_0060(self, hts_hwnd, stock_code, price, qty, account_no=None, telegram=None):
        """0060 화면: 창열기 → 계좌선택 → 비밀번호 → 매수탭 → 종목입력 → 수량입력 → 가격입력 → 현금매수(F1)
        Returns: (alert_sent, order_success) 튜플
        """
        import logging
        _log = logging.getLogger(__name__)
        alert_sent = False
        order_success = False
        with self._block_input():
         try:
            self._close_popups()
            self._set_foreground(hts_hwnd)

            # 1) 0060 화면 열기
            screen_hwnd = self._find_screen_window(hts_hwnd, "0060")
            if not screen_hwnd:
                self.open_screen_no_close(hts_hwnd, "0060")
                screen_hwnd = self._find_screen_window(hts_hwnd, "0060")
            if not screen_hwnd:
                raise RuntimeError("0060 화면을 찾을 수 없습니다.")

            self._maximize_screen(screen_hwnd)
            sr = wintypes.RECT()
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))

            # 2) 계좌 위치 파악 + 비밀번호
            children = self._get_children(screen_hwnd)
            acct_btn = self._find_acct_btn(children, sr)
            acct_y = 0
            if acct_btn:
                ar = wintypes.RECT()
                user32.GetWindowRect(acct_btn, ctypes.byref(ar))
                acct_y = ar.top - sr.top

            # 3) 비밀번호 입력
            self._input_account_password(screen_hwnd, acct_y)
            _log.info(f"[buy_0060] 비밀번호 입력 완료")

            # 4) 매수 탭 선택 (1번째 탭)
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            tab_ctrl = self._find_left_tab(children, sr, acct_y)
            if tab_ctrl:
                tr = wintypes.RECT()
                user32.GetWindowRect(tab_ctrl, ctypes.byref(tr))
                pyautogui.click(tr.left + 15, tr.top + 12)
                self._wait(1)
            # _log.info(f"[buy_0060] tab_ctrl={tab_ctrl}")

            # 5) 종목코드 입력
            children = self._get_children(screen_hwnd)
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            tab_y = 0
            if tab_ctrl:
                tr2 = wintypes.RECT()
                user32.GetWindowRect(tab_ctrl, ctypes.byref(tr2))
                tab_y = tr2.top - sr.top
            code_edit = None
            for h in children:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, cls, 256)
                if cls.value == "iMeritz MaskEdit2":
                    r = wintypes.RECT()
                    user32.GetWindowRect(h, ctypes.byref(r))
                    rx = r.left - sr.left
                    ry = r.top - sr.top
                    w = r.right - r.left
                    if 73 <= w <= 100 and 30 <= rx <= 50 and tab_y < ry < tab_y + 50:
                        code_edit = h
                        break
            if code_edit:
                current_code = self._read_edit_text(code_edit).strip().upper()
                # _log.info(f"[buy_0060] code_edit={code_edit}, current={current_code}, target={stock_code}")
                if current_code != stock_code.upper():
                    r = wintypes.RECT()
                    user32.GetWindowRect(code_edit, ctypes.byref(r))
                    cx = (r.left + r.right) // 2
                    cy = (r.top + r.bottom) // 2
                    pyautogui.doubleClick(cx, cy)
                    self._wait(0.3)
                    pyautogui.typewrite(stock_code, interval=0.05)
                    self._wait(0.3)
                    pyautogui.press("enter")
                    self._wait(1)
            else:
                _log.info("[buy_0060] code_edit not found")

            # 6) 수량 입력
            children = self._get_children(screen_hwnd)
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            code_y = 0
            if code_edit:
                cr = wintypes.RECT()
                user32.GetWindowRect(code_edit, ctypes.byref(cr))
                code_y = cr.top - sr.top
            qty_ctrl = None
            for h in children:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, cls, 256)
                if cls.value == "iMeritz MaskEdit":
                    r = wintypes.RECT()
                    user32.GetWindowRect(h, ctypes.byref(r))
                    rx = r.left - sr.left
                    ry = r.top - sr.top
                    w = r.right - r.left
                    if 65 <= w <= 85 and 35 <= rx <= 50 and code_y + 30 <= ry <= code_y + 70:
                        qty_ctrl = h
                        break
            # _log.info(f"[buy_0060] qty_ctrl={qty_ctrl}")
            if qty_ctrl:
                self._click_control(qty_ctrl)
                self._wait(0.3)
                pyautogui.hotkey("ctrl", "a")
                pyautogui.typewrite(str(qty), interval=0.05)
                self._wait(0.3)

            # 7) 가격 입력
            qty_y = 0
            if qty_ctrl:
                qr = wintypes.RECT()
                user32.GetWindowRect(qty_ctrl, ctypes.byref(qr))
                qty_y = qr.top - sr.top
            price_ctrl = None
            if qty_y:
                for offset in [27, 22, 32, 20, 35]:
                    price_ctrl = self._find_maskedit_by_rel(children, sr, 39, qty_y + offset, 76, tolerance=15)
                    if price_ctrl:
                        break
            # _log.info(f"[buy_0060] price_ctrl={price_ctrl}")
            if price_ctrl:
                self._click_control(price_ctrl)
                self._wait(0.3)
                pyautogui.hotkey("ctrl", "a")
                pyautogui.typewrite(str(price), interval=0.05)
                self._wait(0.3)

            # 8) 현금매수 (F1)
            _log.info("[buy_0060] F1 press")
            pyautogui.press("f1")
            self._wait(1)

            # 확인창 처리
            confirm = self._find_window("매수주문확인팝업", timeout=3)
            if confirm:
                _log.info(f"[buy_0060] 매수주문확인팝업 찾음: {confirm}")
                pyautogui.press("enter")
                self._wait(1)
                # 안내창 뜨면 메시지 텔레그램 전송
                alert = self._find_window("안내", timeout=2)
                if alert:
                    msg = self._read_popup_message(alert)
                    _log.info(f"[buy_0060] 안내창: {msg}")
                    if telegram and msg:
                        telegram.send(f"[매수 안내] {stock_code} {price}/{qty}\n{msg}")
                        alert_sent = True
                    pyautogui.press("enter")
                    self._wait(1)
                    if "영업일" in (msg or ""):
                        _log.info("[buy_0060] 영업일 아님 → HTS 종료 + 프로그램 종료")
                        self.close_hts()
                        sys.exit(0)
                else:
                    # 안내창 없음 = 정상 주문 접수
                    order_success = True
            else:
                _log.info("[buy_0060] 주문확인 못찾음")
         finally:
            self._close_popups()
        return alert_sent, order_success



    def sell_0060(self, hts_hwnd, stock_code, price, qty, account_no=None, telegram=None):
        """0060 화면: 창열기 → 계좌선택 → 비밀번호 → 매도탭 → 종목입력 → 수량입력 → 가격입력 → 현금매도(F2)
        Returns: (alert_sent, order_success) 튜플
        """
        import logging
        _log = logging.getLogger(__name__)
        alert_sent = False
        order_success = False
        with self._block_input():
         try:
            self._close_popups()
            self._set_foreground(hts_hwnd)

            # 1) 0060 화면 열기
            screen_hwnd = self._find_screen_window(hts_hwnd, "0060")
            if not screen_hwnd:
                self.open_screen_no_close(hts_hwnd, "0060")
                screen_hwnd = self._find_screen_window(hts_hwnd, "0060")
            if not screen_hwnd:
                raise RuntimeError("0060 화면을 찾을 수 없습니다.")

            self._maximize_screen(screen_hwnd)
            sr = wintypes.RECT()
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))

            # 2) 계좌 위치 파악 + 비밀번호
            children = self._get_children(screen_hwnd)
            acct_btn = self._find_acct_btn(children, sr)
            acct_y = 0
            if acct_btn:
                ar = wintypes.RECT()
                user32.GetWindowRect(acct_btn, ctypes.byref(ar))
                acct_y = ar.top - sr.top

            # 3) 비밀번호 입력
            self._input_account_password(screen_hwnd, acct_y)
            _log.info(f"[sell_0060] 비밀번호 입력 완료")

            # 4) 매도 탭 선택 (2번째 탭)
            children = self._get_children(screen_hwnd)
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            tab_ctrl = self._find_left_tab(children, sr, acct_y)
            if tab_ctrl:
                tr = wintypes.RECT()
                user32.GetWindowRect(tab_ctrl, ctypes.byref(tr))
                pyautogui.click(tr.left + 45, tr.top + 12)
                self._wait(1)
            # _log.info(f"[sell_0060] tab_ctrl={tab_ctrl}")

            # 5) 종목코드 입력
            children = self._get_children(screen_hwnd)
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            tab_y = 0
            if tab_ctrl:
                tr2 = wintypes.RECT()
                user32.GetWindowRect(tab_ctrl, ctypes.byref(tr2))
                tab_y = tr2.top - sr.top
            code_edit = None
            for h in children:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, cls, 256)
                if cls.value == "iMeritz MaskEdit2":
                    r = wintypes.RECT()
                    user32.GetWindowRect(h, ctypes.byref(r))
                    rx = r.left - sr.left
                    ry = r.top - sr.top
                    w = r.right - r.left
                    if 73 <= w <= 100 and 30 <= rx <= 50 and tab_y < ry < tab_y + 50:
                        code_edit = h
                        break
            if code_edit:
                current_code = self._read_edit_text(code_edit).strip().upper()
                # _log.info(f"[sell_0060] code_edit={code_edit}, current={current_code}, target={stock_code}")
                if current_code != stock_code.upper():
                    r = wintypes.RECT()
                    user32.GetWindowRect(code_edit, ctypes.byref(r))
                    cx = (r.left + r.right) // 2
                    cy = (r.top + r.bottom) // 2
                    pyautogui.doubleClick(cx, cy)
                    self._wait(0.3)
                    pyautogui.typewrite(stock_code, interval=0.05)
                    self._wait(0.3)
                    pyautogui.press("enter")
                    self._wait(1)
            else:
                _log.info("[sell_0060] code_edit not found")

            # 6) 수량 입력
            children = self._get_children(screen_hwnd)
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            code_y = 0
            if code_edit:
                cr = wintypes.RECT()
                user32.GetWindowRect(code_edit, ctypes.byref(cr))
                code_y = cr.top - sr.top
            qty_ctrl = None
            for h in children:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, cls, 256)
                if cls.value == "iMeritz MaskEdit":
                    r = wintypes.RECT()
                    user32.GetWindowRect(h, ctypes.byref(r))
                    rx = r.left - sr.left
                    ry = r.top - sr.top
                    w = r.right - r.left
                    if 65 <= w <= 85 and 35 <= rx <= 50 and code_y + 30 <= ry <= code_y + 70:
                        qty_ctrl = h
                        break
            # _log.info(f"[sell_0060] qty_ctrl={qty_ctrl}")
            if qty_ctrl:
                self._click_control(qty_ctrl)
                self._wait(0.3)
                pyautogui.hotkey("ctrl", "a")
                pyautogui.typewrite(str(qty), interval=0.05)
                self._wait(0.3)

            # 7) 가격 입력
            qty_y = 0
            if qty_ctrl:
                qr = wintypes.RECT()
                user32.GetWindowRect(qty_ctrl, ctypes.byref(qr))
                qty_y = qr.top - sr.top
            price_ctrl = None
            if qty_y:
                for offset in [27, 22, 32, 20, 35]:
                    price_ctrl = self._find_maskedit_by_rel(children, sr, 39, qty_y + offset, 76, tolerance=15)
                    if price_ctrl:
                        break
            # _log.info(f"[sell_0060] price_ctrl={price_ctrl}")
            if price_ctrl:
                self._click_control(price_ctrl)
                self._wait(0.3)
                pyautogui.hotkey("ctrl", "a")
                pyautogui.typewrite(str(price), interval=0.05)
                self._wait(0.3)

            # 8) 현금매도 (F2)
            _log.info("[sell_0060] F2 press")
            pyautogui.press("f2")
            self._wait(1)

            # 확인창 처리
            confirm = self._find_window("매도주문확인팝업", timeout=3)
            if confirm:
                _log.info(f"[sell_0060] 매도주문확인팝업 찾음: {confirm}")
                pyautogui.press("enter")
                self._wait(1)
                # 안내창 뜨면 메시지 텔레그램 전송
                alert = self._find_window("안내", timeout=2)
                if alert:
                    msg = self._read_popup_message(alert)
                    _log.info(f"[sell_0060] 안내창: {msg}")
                    if telegram and msg:
                        telegram.send(f"[매도 안내] {stock_code} {price}/{qty}\n{msg}")
                        alert_sent = True
                    pyautogui.press("enter")
                    self._wait(1)
                    if "영업일" in (msg or ""):
                        _log.info("[sell_0060] 영업일 아님 → HTS 종료 + 프로그램 종료")
                        self.close_hts()
                        sys.exit(0)
                else:
                    # 안내창 없음 = 정상 주문 접수
                    order_success = True
            else:
                _log.info("[sell_0060] 주문확인 못찾음")
         finally:
            self._close_popups()
        return alert_sent, order_success

    def cancel_all_0060(self, hts_hwnd, stock_code=None, account_no=None):
        """0060 화면: 하단 미체결 탭 → 전체선택 → 일괄취소. stock_code 지정 시 해당 종목 미체결만 취소."""
        import logging
        _log = logging.getLogger(__name__)
        with self._block_input():
         try:
            self._close_popups()
            self._set_foreground(hts_hwnd)

            # 1) 0060 화면 열기
            screen_hwnd = self._find_screen_window(hts_hwnd, "0060")
            if not screen_hwnd:
                self.open_screen_no_close(hts_hwnd, "0060")
                screen_hwnd = self._find_screen_window(hts_hwnd, "0060")
            if not screen_hwnd:
                raise RuntimeError("0060 화면을 찾을 수 없습니다.")

            self._maximize_screen(screen_hwnd)
            sr = wintypes.RECT()
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            # _log.info(f"[cancel_0060] screen_rect=({sr.left},{sr.top},{sr.right},{sr.bottom})")

            # 2) 계좌 선택 + 비밀번호
            children = self._get_children(screen_hwnd)
            acct_btn = self._find_acct_btn(children, sr)
            acct_y = 0
            if acct_btn:
                ar = wintypes.RECT()
                user32.GetWindowRect(acct_btn, ctypes.byref(ar))
                acct_y = ar.top - sr.top

            self._input_account_password(screen_hwnd, acct_y)
            _log.info("[cancel_0060] 비밀번호 입력 완료")

            # 3) 하단 오른쪽 탭 찾기 → 첫번째 탭(미체결) 클릭
            children = self._get_children(screen_hwnd)
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            bottom_tab = self._find_bottom_right_tab(children, sr)
            if not bottom_tab:
                _log.info("[cancel_0060] 하단 탭 못찾음")
                return
            btr = wintypes.RECT()
            user32.GetWindowRect(bottom_tab, ctypes.byref(btr))
            # _log.info(f"[cancel_0060] bottom_tab rect=({btr.left},{btr.top},{btr.right},{btr.bottom}), 클릭좌표=({btr.left+30},{btr.top+12})")
            # 스크린샷으로 탭 영역 확인
            pyautogui.click(btr.left + 57, btr.top + 11)
            self._wait(1)
            _log.info("[cancel_0060] 미체결 탭 클릭")


            # 그리드 찾기
            children = self._get_children(screen_hwnd)
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            tab_ry = btr.top - sr.top
            grid_hwnd = self._find_grid(children, sr, tab_ry)

            if stock_code and grid_hwnd:
                # 행별로 클릭하며 종목 확인 → 대상 종목만 체크박스 클릭
                gr = wintypes.RECT()
                user32.GetWindowRect(grid_hwnd, ctypes.byref(gr))
                row_height = 20
                header_height = 20
                max_rows = (gr.bottom - gr.top - header_height) // row_height
                found = False
                prev_text = ""
                for i in range(max_rows):
                    row_y = gr.top + header_height + i * row_height + row_height // 2
                    # 행 클릭 (종목코드 열 위치)
                    pyautogui.click(gr.left + 100, row_y)
                    self._wait(0.3)
                    # MaskEdit에서 종목코드 읽기
                    children2 = self._get_children(screen_hwnd)
                    cur_text = ""
                    row_stock = None
                    for h in children2:
                        cls = ctypes.create_unicode_buffer(256)
                        user32.GetClassNameW(h, cls, 256)
                        if cls.value == "iMeritz MaskEdit":
                            text = self._read_edit_text(h)
                            if text and "주식미체결" in text:
                                cur_text = text
                                parts = text.split("|")
                                if len(parts) >= 3:
                                    row_stock = parts[2].upper()
                                break
                    # 빈 행 감지: 데이터 없거나 이전 행과 동일하면 중단
                    if not row_stock or (i > 0 and cur_text == prev_text):
                        break
                    prev_text = cur_text
                    if row_stock == stock_code.upper():
                        # 체크박스 클릭
                        pyautogui.click(gr.left + 32, row_y)
                        self._wait(0.3)
                        found = True
                        _log.info(f"[cancel_0060] {stock_code} 행[{i}] 체크")
                if not found:
                    _log.info(f"[cancel_0060] {stock_code} 미체결 없음, 스킵")
                    return
            else:
                # 전체선택: 그리드 체크박스 열 클릭 (gr.left + 32, 헤더 중간)
                if grid_hwnd:
                    gr2 = wintypes.RECT()
                    user32.GetWindowRect(grid_hwnd, ctypes.byref(gr2))
                    pyautogui.click(gr2.left + 32, gr2.top + 10)
                else:
                    pyautogui.click(sr.left + 387, sr.top + 393)
                self._wait(1)
                _log.info("[cancel_0060] 전체선택 체크박스 클릭")

            # 5) "일괄취소" 버튼 클릭 - 하단 탭 AfxWnd90 내부 버튼 (rx~134, ry~5, w~52, h~23)
            children = self._get_children(screen_hwnd)
            user32.GetWindowRect(screen_hwnd, ctypes.byref(sr))
            cancel_btn = None
            # 하단 탭 영역(AfxWnd90) 찾기
            for h in children:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, cls, 256)
                if cls.value == "AfxWnd90":
                    r = wintypes.RECT()
                    user32.GetWindowRect(h, ctypes.byref(r))
                    ry = r.top - sr.top
                    w = r.right - r.left
                    if ry > 270 and w > 500:
                        # 이 AfxWnd90 내부에서 일괄취소 버튼 찾기 (rx~134, ry~5, w~52)
                        sub_children = self._get_children(h)
                        ar = wintypes.RECT()
                        user32.GetWindowRect(h, ctypes.byref(ar))
                        for sh in sub_children:
                            scls = ctypes.create_unicode_buffer(256)
                            user32.GetClassNameW(sh, scls, 256)
                            if scls.value == "Button" and user32.IsWindowVisible(sh):
                                br = wintypes.RECT()
                                user32.GetWindowRect(sh, ctypes.byref(br))
                                brx = br.left - ar.left
                                bry = br.top - ar.top
                                bw = br.right - br.left
                                bh = br.bottom - br.top
                                if 100 <= brx <= 170 and bry <= 15 and 40 <= bw <= 70 and 18 <= bh <= 30:
                                    cancel_btn = sh
                                    break
                        if cancel_btn:
                            break
            if cancel_btn:
                _log.info(f"[cancel_0060] 일괄취소 버튼 찾음: {cancel_btn}")
                self._click_control(cancel_btn)
            else:
                # 폴백: bottom_tab 기준 좌표 클릭
                _log.info("[cancel_0060] 일괄취소 버튼 못찾음, 좌표 클릭")
                pyautogui.click(btr.left + 134 + 26, btr.top + 26 + 5 + 11)
            self._wait(1)
            _log.info("[cancel_0060] 일괄취소 버튼 클릭")

            # 6) 취소주문확인 팝업 처리
            confirm = self._find_window("해외주식 일괄 취소주문 확인창", timeout=3)
            if confirm:
                _log.info(f"[cancel_0060] 취소확인창 찾음: {confirm}")
                cr = wintypes.RECT()
                user32.GetWindowRect(confirm, ctypes.byref(cr))
                # "취소주문" 버튼 클릭 시도
                btn = self._find_button_recursive(confirm, "취소주문")
                if btn:
                    _log.info(f"[cancel_0060] 취소주문 버튼 찾음: {btn}")
                    self._click_control(btn)
                else:
                    # BM_CLICK 폴백: 버튼 인덱스 3 = 취소주문
                    popup_btns = self._get_visible_buttons(confirm)
                    if len(popup_btns) > 3:
                        _log.info(f"[cancel_0060] BM_CLICK으로 취소주문 버튼 클릭 (idx=3)")
                        user32.PostMessageW(popup_btns[3], 0x00F5, 0, 0)
                    else:
                        pyautogui.click(cr.left + 270, cr.top + 288)
                self._wait(1)
                _log.info("[cancel_0060] 취소주문 버튼 클릭")
                # 창이 남아있으면 "닫기" 버튼 클릭
                if user32.IsWindow(confirm) and user32.IsWindowVisible(confirm):
                    btn2 = self._find_button_recursive(confirm, "닫기")
                    if btn2:
                        self._click_control(btn2)
                    else:
                        # BM_CLICK 폴백: 버튼 인덱스 2 = 닫기
                        popup_btns = self._get_visible_buttons(confirm)
                        if len(popup_btns) > 2:
                            _log.info(f"[cancel_0060] BM_CLICK으로 닫기 버튼 클릭 (idx=2)")
                            user32.PostMessageW(popup_btns[2], 0x00F5, 0, 0)
                        else:
                            pyautogui.click(cr.left + 331, cr.top + 288)
                    self._wait(0.5)
                    _log.info("[cancel_0060] 닫기 버튼 클릭")
            else:
                # 취소할 항목 없을 때 안내창 처리
                alert = self._find_window("종목확인", timeout=1)
                if not alert:
                    alert = self._find_window("안내", timeout=1)
                if alert:
                    _log.info(f"[cancel_0060] 안내창 찾음: {alert}")
                    pyautogui.press("enter")
                    self._wait(1)
                else:
                    _log.info("[cancel_0060] 취소확인창 못찾음")

         finally:
            self._close_popups()

    def _read_popup_message(self, popup_hwnd):
        """팝업 창에서 Static 텍스트(안내 메시지)를 읽는다."""
        children = self._get_children(popup_hwnd)
        texts = []
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == "Static":
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    texts.append(buf.value)
        return "\n".join(texts)

    def _close_popups(self):
        """남아있는 팝업(안내, 확인, 오류 등)을 모두 닫는다."""
        # HTS 내부 공지사항 화면 닫기
        main = self._find_window("iMeritz", timeout=0.5)
        if main:
            children = self._get_children(main)
            for child in children:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(child, cls, 256)
                if cls.value == "ITGEN_SCREEN_WINDOW":
                    length = user32.GetWindowTextLengthW(child)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(child, buf, length + 1)
                        if "공지" in buf.value:
                            user32.PostMessageW(child, 0x0010, 0, 0)  # WM_CLOSE
                            self._wait(0.3)
                            break
        # 팝업을 한 번에 스캔 (EnumWindows 1회)
        popups = []
        keywords = ["안내", "확인", "오류", "알림", "로드", "공지사항", "MeritzMain"]
        def cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                for kw in keywords:
                    if kw in buf.value:
                        popups.append(hwnd)
                        break
            return True
        user32.EnumWindows(WNDENUMPROC(cb), 0)
        for popup in popups:
            if not user32.IsWindowVisible(popup):
                continue
            self._set_foreground(popup)
            btn = self._find_button_recursive(popup, "확인")
            if not btn:
                btn = self._find_button_recursive(popup, "닫기")
            if btn:
                self._click_button(btn)
            else:
                children = self._get_children(popup)
                clicked = False
                for child in children:
                    cls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(child, cls, 256)
                    if cls.value == "Button" and user32.IsWindowVisible(child):
                        self._click_control(child)
                        clicked = True
                        break
                if not clicked:
                    pyautogui.press("enter")
            self._wait(0.2)


    def _find_edit_by_size(self, children, min_w, max_w, min_h, max_h, exclude=None):
        """크기 범위로 Edit 컨트롤을 찾는다."""
        for hwnd in children:
            if exclude and hwnd in exclude:
                continue
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == "Edit":
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if min_w <= w <= max_w and min_h <= h <= max_h:
                    return hwnd
        return None

    def _find_edit_near(self, children, ref_x, ref_y, max_dist):
        """기준 좌표 근처의 Edit 컨트롤을 찾는다."""
        for hwnd in children:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value == "Edit":
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                cx = (rect.left + rect.right) // 2
                cy = (rect.top + rect.bottom) // 2
                if abs(cx - ref_x) < max_dist and abs(cy - ref_y) < max_dist:
                    return hwnd
        return None

    def _read_edit_text(self, hwnd):
        """Edit 컨트롤에서 텍스트를 읽는다."""
        WM_GETTEXT = 0x000D
        WM_GETTEXTLENGTH = 0x000E
        length = ctypes.c_long(user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)).value
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.SendMessageW(hwnd, WM_GETTEXT, length + 1, ctypes.addressof(buf))
        return buf.value

    def _find_window(self, keyword, timeout=5):
        result = [None]
        def cb(hwnd, _):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if keyword in buf.value:
                    result[0] = hwnd
                    return False
            return True
        def _check():
            result[0] = None
            user32.EnumWindows(WNDENUMPROC(cb), 0)
            return result[0]
        return self._wait_until(_check, timeout=timeout, interval=0.3)

    def _find_popup(self, title, timeout=3):
        """타이틀이 정확히 일치하는 visible 팝업 창을 찾는다."""
        for _ in range(timeout * 2):
            result = [None]
            def cb(hwnd, _):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if buf.value == title:
                        result[0] = hwnd
                        return False
                return True
            user32.EnumWindows(WNDENUMPROC(cb), 0)
            if result[0]:
                return result[0]
            time.sleep(0.5)
        return None


def _type_text(text):
    """pyautogui.write 대신 한 글자씩 직접 입력"""
    for ch in text:
        if ch.isupper():
            pyautogui.hotkey("shift", ch.lower())
        elif ch in SHIFT_MAP:
            pyautogui.hotkey("shift", SHIFT_MAP[ch])
        else:
            pyautogui.press(ch)
        time.sleep(0.05)


SHIFT_MAP = {
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5',
    '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
    '_': '-', '+': '=', '{': '[', '}': ']', '|': '\\',
    ':': ';', '"': "'", '<': ',', '>': '.', '?': '/',
    '~': '`',
}
