"""자동매매 실행 (관리자 권한 자동 승격)"""
import sys
import os
import ctypes


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if __name__ == "__main__":
    # EXE/스크립트 위치로 CWD 강제 설정
    if getattr(sys, 'frozen', False):
        _base = os.path.dirname(sys.executable)
    else:
        _base = os.path.dirname(os.path.abspath(__file__))
    os.chdir(_base)

    if not is_admin():
        if getattr(sys, 'frozen', False):
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, None, _base, 1
            )
        else:
            script = os.path.abspath(__file__)
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}"', _base, 1
            )
        sys.exit(0)

    from trader import AutoTrader
    try:
        trader = AutoTrader()
        trader.run()
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("엔터를 누르면 종료합니다...")
