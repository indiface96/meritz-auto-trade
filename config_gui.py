"""config.json 환경설정 GUI"""
import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QSpinBox, QFileDialog, QGroupBox,
    QListWidget, QMessageBox, QLabel,
)
from PyQt5.QtCore import Qt

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
MAX_ACCOUNTS = 4


def load_json():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "hts_path": "", "accounts": [],
        "google_sheet": {"credentials_file": "credentials.json", "spreadsheet_id": ""},
        "check_interval_minutes": 5, "sheet_names": [],
    }


def save_json(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


class ConfigGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_json()
        self.setWindowTitle("키움 자동매매 환경설정")
        self.setMinimumWidth(520)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # HTS 경로
        grp_hts = QGroupBox("HTS 경로")
        h = QHBoxLayout(grp_hts)
        self.edit_hts = QLineEdit()
        btn_hts = QPushButton("찾기")
        btn_hts.clicked.connect(self._browse_hts)
        h.addWidget(self.edit_hts)
        h.addWidget(btn_hts)
        root.addWidget(grp_hts)

        # 키움 계정
        grp_acc = QGroupBox(f"키움 계정 (최대 {MAX_ACCOUNTS}개)")
        v = QVBoxLayout(grp_acc)
        self.list_acc = QListWidget()
        v.addWidget(self.list_acc)
        h2 = QHBoxLayout()
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("인증서 이름")
        self.edit_idx = QSpinBox()
        self.edit_idx.setRange(0, 10)
        self.edit_idx.setPrefix("순번: ")
        self.edit_pw = QLineEdit()
        self.edit_pw.setPlaceholderText("인증서 비밀번호")
        self.edit_pw.setEchoMode(QLineEdit.Password)
        btn_add = QPushButton("추가")
        btn_add.clicked.connect(self._add_account)
        btn_del = QPushButton("삭제")
        btn_del.clicked.connect(self._del_account)
        for w in (self.edit_name, self.edit_idx, self.edit_pw, btn_add, btn_del):
            h2.addWidget(w)
        v.addLayout(h2)
        root.addWidget(grp_acc)

        # 구글 시트
        grp_gs = QGroupBox("구글 시트")
        form = QFormLayout(grp_gs)
        h3 = QHBoxLayout()
        self.edit_cred = QLineEdit()
        btn_cred = QPushButton("찾기")
        btn_cred.clicked.connect(self._browse_cred)
        h3.addWidget(self.edit_cred)
        h3.addWidget(btn_cred)
        form.addRow("Credentials 파일:", h3)
        self.edit_sid = QLineEdit()
        form.addRow("Spreadsheet ID:", self.edit_sid)
        root.addWidget(grp_gs)

        # 시트 이름
        grp_sn = QGroupBox("시트 설정")
        v2 = QVBoxLayout(grp_sn)
        self.list_sheets = QListWidget()
        v2.addWidget(self.list_sheets)
        h4 = QHBoxLayout()
        self.edit_sheet = QLineEdit()
        self.edit_sheet.setPlaceholderText("시트 이름")
        self.edit_sheet_interval = QSpinBox()
        self.edit_sheet_interval.setRange(1, 30)
        self.edit_sheet_interval.setPrefix("주기: ")
        self.edit_sheet_interval.setSuffix("분")
        self.edit_sheet_interval.setValue(5)
        self.edit_sheet_end = QLineEdit()
        self.edit_sheet_end.setPlaceholderText("종료시간 (HH:MM)")
        self.edit_sheet_end.setMaximumWidth(100)
        btn_sadd = QPushButton("추가")
        btn_sadd.clicked.connect(self._add_sheet)
        btn_sdel = QPushButton("삭제")
        btn_sdel.clicked.connect(self._del_sheet)
        h4.addWidget(self.edit_sheet)
        h4.addWidget(self.edit_sheet_interval)
        h4.addWidget(self.edit_sheet_end)
        h4.addWidget(btn_sadd)
        h4.addWidget(btn_sdel)
        v2.addLayout(h4)
        root.addWidget(grp_sn)

        # 프로그램 종료시간
        h_end = QHBoxLayout()
        h_end.addWidget(QLabel("프로그램 종료시간:"))
        self.edit_program_end = QLineEdit()
        self.edit_program_end.setPlaceholderText("HH:MM")
        self.edit_program_end.setMaximumWidth(80)
        h_end.addWidget(self.edit_program_end)
        h_end.addStretch()
        root.addLayout(h_end)

        # 확인 주기
        h5 = QHBoxLayout()
        h5.addWidget(QLabel("기본 확인 주기(분):"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 30)
        h5.addWidget(self.spin_interval)
        h5.addStretch()
        root.addLayout(h5)

        # 속도 배수 (느린 PC용)
        h_speed = QHBoxLayout()
        h_speed.addWidget(QLabel("속도 배수:"))
        self.spin_speed = QSpinBox()
        self.spin_speed.setRange(1, 5)
        self.spin_speed.setToolTip("느린 PC에서는 2~3으로 설정 (대기 시간이 배수만큼 늘어남)")
        h_speed.addWidget(self.spin_speed)
        h_speed.addWidget(QLabel("(느린 PC: 2~3)"))
        h_speed.addStretch()
        root.addLayout(h_speed)

        # 테스트 모드
        from PyQt5.QtWidgets import QComboBox
        h_test = QHBoxLayout()
        h_test.addWidget(QLabel("테스트 모드:"))
        self.combo_test = QComboBox()
        self.combo_test.addItems(["N", "Y"])
        self.combo_test.setToolTip("Y: 체결 안되게 20% 여유 / N: 실제 매매")
        h_test.addWidget(self.combo_test)
        h_test.addWidget(QLabel("(Y: 체결방지, N: 실매매)"))
        h_test.addStretch()
        root.addLayout(h_test)

        # 하단 버튼
        h6 = QHBoxLayout()
        btn_run_now = QPushButton("바로 실행")
        btn_run_now.clicked.connect(self._run_now)
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self._save)
        btn_run = QPushButton("저장 후 실행")
        btn_run.clicked.connect(self._save_and_run)
        h6.addWidget(btn_run_now)
        h6.addStretch()
        h6.addWidget(btn_save)
        h6.addWidget(btn_run)
        root.addLayout(h6)

    def _load_values(self):
        self.edit_hts.setText(self.cfg.get("hts_path", ""))
        for acc in self.cfg.get("accounts", []):
            self.list_acc.addItem(f"{acc['cert_name']} (순번:{acc['cert_index']})")
        gs = self.cfg.get("google_sheet", {})
        self.edit_cred.setText(gs.get("credentials_file", ""))
        self.edit_sid.setText(gs.get("spreadsheet_id", ""))
        for s in self.cfg.get("sheet_names", []):
            if isinstance(s, dict):
                self.list_sheets.addItem(f"{s['name']} | {s.get('check_interval_minutes',5)}분 | {s.get('trade_end_time','15:30')}")
            else:
                self.list_sheets.addItem(s)
        self.spin_interval.setValue(self.cfg.get("check_interval_minutes", 5))
        self.spin_speed.setValue(int(self.cfg.get("speed_multiplier", 1)))
        self.edit_program_end.setText(self.cfg.get("program_end_time", "15:40"))
        self.combo_test.setCurrentText(self.cfg.get("test_only", "N"))

    def _browse_hts(self):
        path, _ = QFileDialog.getOpenFileName(self, "HTS 실행파일 선택", "", "실행파일 (*.exe)")
        if path:
            self.edit_hts.setText(path)

    def _browse_cred(self):
        path, _ = QFileDialog.getOpenFileName(self, "Credentials 파일 선택", BASE_DIR, "JSON (*.json)")
        if path:
            self.edit_cred.setText(os.path.basename(path))

    def _add_account(self):
        name = self.edit_name.text().strip()
        pw = self.edit_pw.text().strip()
        if not name or not pw:
            return QMessageBox.warning(self, "입력 오류", "이름과 비밀번호를 입력하세요.")
        accs = self.cfg.setdefault("accounts", [])
        if len(accs) >= MAX_ACCOUNTS:
            return QMessageBox.warning(self, "제한 초과", f"최대 {MAX_ACCOUNTS}개까지 가능합니다.")
        acc = {"cert_name": name, "cert_index": self.edit_idx.value(), "cert_password": pw}
        accs.append(acc)
        self.list_acc.addItem(f"{name} (순번:{acc['cert_index']})")
        self.edit_name.clear()
        self.edit_pw.clear()

    def _del_account(self):
        row = self.list_acc.currentRow()
        if row >= 0:
            self.list_acc.takeItem(row)
            self.cfg["accounts"].pop(row)

    def _add_sheet(self):
        name = self.edit_sheet.text().strip()
        if not name:
            return
        interval = self.edit_sheet_interval.value()
        end_time = self.edit_sheet_end.text().strip() or "15:30"
        entry = {"name": name, "check_interval_minutes": interval, "trade_end_time": end_time}
        self.cfg.setdefault("sheet_names", []).append(entry)
        self.list_sheets.addItem(f"{name} | {interval}분 | {end_time}")
        self.edit_sheet.clear()
        self.edit_sheet_end.clear()

    def _del_sheet(self):
        row = self.list_sheets.currentRow()
        if row >= 0:
            self.list_sheets.takeItem(row)
            self.cfg["sheet_names"].pop(row)

    def _collect(self):
        self.cfg["hts_path"] = self.edit_hts.text().strip()
        self.cfg["google_sheet"] = {
            "credentials_file": self.edit_cred.text().strip(),
            "spreadsheet_id": self.edit_sid.text().strip(),
        }
        self.cfg["check_interval_minutes"] = self.spin_interval.value()
        self.cfg["speed_multiplier"] = float(self.spin_speed.value())
        self.cfg["program_end_time"] = self.edit_program_end.text().strip() or "15:40"
        self.cfg["test_only"] = self.combo_test.currentText()

    def _launch_trader(self):
        import ctypes
        main_path = os.path.join(BASE_DIR, "main.py")
        exe_path = os.path.join(BASE_DIR, "메리츠자동매매.exe")
        if os.path.exists(exe_path):
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", exe_path, None, BASE_DIR, 1
            )
        elif os.path.exists(main_path):
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{main_path}"', BASE_DIR, 1
            )
        else:
            QMessageBox.warning(self, "실행 오류", "실행 파일을 찾을 수 없습니다.")
            return False
        return True

    def _run_now(self):
        if self._launch_trader():
            self.close()

    def _save(self):
        self._collect()
        save_json(self.cfg)
        QMessageBox.information(self, "저장 완료", "config.json이 저장되었습니다.")

    def _save_and_run(self):
        self._collect()
        save_json(self.cfg)
        if self._launch_trader():
            self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ConfigGUI()
    w.show()
    sys.exit(app.exec_())
