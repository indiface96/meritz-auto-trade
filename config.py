import json
import os
import sys

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")
MAX_KIWOOM_USERS = 4
MIN_INTERVAL = 1
MAX_INTERVAL = 30


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if len(cfg.get("accounts", [])) > MAX_KIWOOM_USERS:
        raise ValueError(f"키움 계정은 최대 {MAX_KIWOOM_USERS}개까지 설정 가능합니다.")
    interval = cfg.get("check_interval_minutes", MIN_INTERVAL)
    if not (MIN_INTERVAL <= interval <= MAX_INTERVAL):
        raise ValueError(f"확인 주기는 {MIN_INTERVAL}~{MAX_INTERVAL}분 사이여야 합니다.")
    return cfg
