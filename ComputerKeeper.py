import sys
import os
import time
import random
import ctypes
import datetime
from ctypes import wintypes
from PyQt5 import QtWidgets, QtCore, QtGui

def resource_path(relative_path: str) -> str:
    # PyInstaller 一文件模式下的运行时临时目录在 sys._MEIPASS
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

IS_WINDOWS = sys.platform.startswith("win")

# Windows 常量与 API
if IS_WINDOWS:
    import winreg

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_WHEEL = 0x0800
    KEYEVENTF_KEYUP = 0x0002
    VK_SHIFT = 0x10

    WM_INPUT = 0x00FF
    RIDEV_INPUTSINK = 0x00000100
    RIM_TYPEMOUSE = 0
    RIM_TYPEKEYBOARD = 1
    RID_HEADER = 0x10000005

    class RAWINPUTDEVICE(ctypes.Structure):
        _fields_ = [
            ("usUsagePage", wintypes.USHORT),
            ("usUsage", wintypes.USHORT),
            ("dwFlags", wintypes.DWORD),
            ("hwndTarget", wintypes.HWND),
        ]

    class RAWINPUTHEADER(ctypes.Structure):
        _fields_ = [
            ("dwType", wintypes.DWORD),
            ("dwSize", wintypes.DWORD),
            ("hDevice", wintypes.HANDLE),
            ("wParam", wintypes.WPARAM),
        ]

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", POINT),
        ]

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

def enable_keep_awake():
    if IS_WINDOWS:
        kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )

def disable_keep_awake():
    if IS_WINDOWS:
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)

def get_idle_seconds_win32():
    if not IS_WINDOWS:
        return 0.0
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(lii)
    if not user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0.0
    tick_now = kernel32.GetTickCount()
    diff = (tick_now - lii.dwTime) & 0xFFFFFFFF
    return diff / 1000.0

class MouseMover(QtWidgets.QWidget):
    def __init__(self):
        super(MouseMover, self).__init__()

        # 打包后使用 EXE 所在目录；直接运行源码时使用脚本所在目录。
        program_path = sys.executable if getattr(sys, "frozen", False) else __file__
        self.settings_path = os.path.join(os.path.dirname(os.path.abspath(program_path)), "ComputerKeeper.ini")

        self.setWindowTitle("ComputerKeeper")
        self.setObjectName("keeperWindow")
        self.resize(600, 720)
        self.setMinimumSize(560, 700)
        self.setWindowIcon(QtGui.QIcon(resource_path("icon.png")))
        self._apply_theme()

        # 使用布局管理器统一间距，适应窗口缩放和不同系统字体。
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel('ComputerKeeper', self)
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        badge = QtWidgets.QLabel('DESKTOP ASSISTANT', self)
        badge.setObjectName("badge")
        header.addWidget(badge)
        layout.addLayout(header)

        # 开机自启独占首个设置区，不与触发参数混排。
        startup_card, startup_layout = self._create_card()
        self.startupCheck = QtWidgets.QCheckBox('开机自启', self)
        self.startupCheck.setEnabled(IS_WINDOWS)
        startup_layout.addWidget(self.startupCheck)
        startup_hint = QtWidgets.QLabel('登录 Windows 后自动打开 · 点击保存后生效', self)
        startup_hint.setObjectName("muted")
        startup_layout.addWidget(startup_hint)
        layout.addWidget(startup_card)

        schedule_card, schedule_layout = self._create_card()
        schedule_title = QtWidgets.QLabel('运行计划', self)
        schedule_title.setObjectName("sectionTitle")
        schedule_layout.addWidget(schedule_title)
        schedule_grid = QtWidgets.QGridLayout()
        schedule_grid.setHorizontalSpacing(16)
        schedule_grid.setVerticalSpacing(12)
        self.startLabel = QtWidgets.QLabel('开始时间', self)
        self.endLabel = QtWidgets.QLabel('结束时间', self)
        self.startTimeEdit = QtWidgets.QTimeEdit(self)
        self.endTimeEdit = QtWidgets.QTimeEdit(self)
        self.startTimeEdit.setTime(QtCore.QTime(9, 0))
        self.endTimeEdit.setTime(QtCore.QTime(17, 55))
        for editor in (self.startTimeEdit, self.endTimeEdit):
            editor.setDisplayFormat("HH:mm")
            editor.setMinimumHeight(38)
        schedule_grid.addWidget(self.startLabel, 0, 0)
        schedule_grid.addWidget(self.startTimeEdit, 0, 1)
        schedule_grid.addWidget(self.endLabel, 0, 2)
        schedule_grid.addWidget(self.endTimeEdit, 0, 3)
        self.lunchLabel = QtWidgets.QLabel('午休时段', self)
        self.lunchStartEdit = QtWidgets.QTimeEdit(self)
        self.lunchEndEdit = QtWidgets.QTimeEdit(self)
        self.lunchStartEdit.setTime(QtCore.QTime(12, 0))
        self.lunchEndEdit.setTime(QtCore.QTime(13, 30))
        for editor in (self.lunchStartEdit, self.lunchEndEdit):
            editor.setDisplayFormat("HH:mm")
            editor.setMinimumHeight(38)
        self.lunchSepLabel = QtWidgets.QLabel('至', self)
        self.lunchSepLabel.setAlignment(QtCore.Qt.AlignCenter)
        schedule_grid.addWidget(self.lunchLabel, 1, 0)
        schedule_grid.addWidget(self.lunchStartEdit, 1, 1)
        schedule_grid.addWidget(self.lunchSepLabel, 1, 2)
        schedule_grid.addWidget(self.lunchEndEdit, 1, 3)
        schedule_grid.setColumnStretch(1, 1)
        schedule_grid.setColumnStretch(3, 1)
        schedule_layout.addLayout(schedule_grid)
        days_layout = QtWidgets.QHBoxLayout()
        days_layout.setSpacing(6)
        self.dayChecks = []
        for day, name in enumerate(("周一", "周二", "周三", "周四", "周五", "周六", "周日")):
            checkbox = QtWidgets.QCheckBox(name, self)
            checkbox.setObjectName("dayCheck")
            checkbox.setChecked(day < 5)
            days_layout.addWidget(checkbox, 1)
            self.dayChecks.append(checkbox)
        schedule_layout.addLayout(days_layout)
        days_hint = QtWidgets.QLabel('全不选时仅当天有效；午休期间暂停执行。', self)
        days_hint.setObjectName("muted")
        schedule_layout.addWidget(days_hint)
        layout.addWidget(schedule_card)

        activity_card, activity_layout = self._create_card()
        activity_title = QtWidgets.QLabel('触发设置', self)
        activity_title.setObjectName("sectionTitle")
        activity_layout.addWidget(activity_title)
        activity_grid = QtWidgets.QGridLayout()
        activity_grid.setHorizontalSpacing(12)
        activity_grid.setVerticalSpacing(12)
        self.intervalLabel = QtWidgets.QLabel('间隔时间（秒）', self)
        self.intervalLineEdit = QtWidgets.QLineEdit(self)
        self.intervalLineEdit.setPlaceholderText("建议 ≥ 20")
        self.intervalLineEdit.setText("30")
        self.intervalLineEdit.setValidator(QtGui.QIntValidator(1, 86400, self))
        interval_tip = (
            "<p><b>间隔时间（秒）</b></p>"
            "<p>空闲达到阈值、进入模拟状态后，两次模拟键鼠操作之间的间隔。</p>"
            "<p>实际间隔按设定值的 70%～130% 随机浮动；小于 3 秒时按 3 秒计算。<br>"
            "例如设为 30 秒，实际约每 21～39 秒模拟一次。</p>"
            "<p>仅在所选星期和运行时间内执行，午休期间暂停。</p>"
        )
        self.intervalHelp = self._create_help_icon(interval_tip)
        self.idleLabel = QtWidgets.QLabel('空闲触发（分钟）', self)
        self.idleMinutesSpin = QtWidgets.QSpinBox(self)
        self.idleMinutesSpin.setRange(1, 240)
        self.idleMinutesSpin.setValue(5)
        idle_tip = (
            "<p><b>空闲触发（分钟）</b></p>"
            "<p>连续多久没有键鼠操作后，程序才开始模拟操作。<br>"
            "例如设为 5 分钟，连续空闲达到 5 分钟后才会触发。</p>"
            "<p>等待空闲时约每 15 秒检查一次，并非刚到阈值就立即触发。<br>"
            "检测到键鼠操作后暂停模拟，等待再次空闲。</p>"
            "<p>需要先点击“开始”，且处于所选星期和运行时段内；午休期间暂停。</p>"
        )
        self.idleHelp = self._create_help_icon(idle_tip)
        for row, (label, editor, help_icon) in enumerate((
            (self.intervalLabel, self.intervalLineEdit, self.intervalHelp),
            (self.idleLabel, self.idleMinutesSpin, self.idleHelp),
        )):
            editor.setMinimumHeight(38)
            activity_grid.addWidget(label, row, 0)
            activity_grid.addWidget(editor, row, 1)
            activity_grid.addWidget(help_icon, row, 2)
        activity_grid.setColumnStretch(1, 1)
        activity_layout.addLayout(activity_grid)
        layout.addWidget(activity_card)
        layout.addStretch()

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(12)
        self.startButton = QtWidgets.QPushButton('开始', self)
        self.startButton.setObjectName("primaryButton")
        self.startButton.clicked.connect(self.start_moving)
        self.stopButton = QtWidgets.QPushButton('停止', self)
        self.stopButton.setObjectName("stopButton")
        self.stopButton.clicked.connect(self.stop_moving)
        self.stopButton.setEnabled(False)
        self.saveButton = QtWidgets.QPushButton('保存设置', self)
        self.saveButton.clicked.connect(self.save_settings)
        for button in (self.startButton, self.stopButton, self.saveButton):
            button.setMinimumHeight(42)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            actions.addWidget(button, 1)
        layout.addLayout(actions)
        self.statusLabel = QtWidgets.QLabel('状态：待机', self)
        self.statusLabel.setObjectName("statusLabel")
        self.statusLabel.setWordWrap(True)
        self.statusLabel.setMinimumHeight(46)
        layout.addWidget(self.statusLabel)

        # 定时器
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_timer)

        # 先恢复所有设置控件，再初始化本次运行使用的参数。
        self._load_settings()

        # 运行状态
        self.running = False
        self.active_mode = False
        self.interval_seconds = int(self.intervalLineEdit.text())
        self.start_time = self.startTimeEdit.time()
        self.end_time = self.endTimeEdit.time()
        self.lunch_start = self.lunchStartEdit.time()
        self.lunch_end = self.lunchEndEdit.time()
        self.idle_minutes_threshold = self.idleMinutesSpin.value()

        # “当天有效”模式
        self.no_day_selected = False
        self.anchor_date = None

        # Raw Input
        self.raw_input_registered = False
        self.use_raw_input = False
        self.last_user_input_ts = time.monotonic()

        # 托盘
        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        self.tray_icon.setIcon(QtGui.QIcon(resource_path("icon.png")))
        self.tray_icon.setVisible(True)

        self.tray_menu = QtWidgets.QMenu(self)
        self.show_action = self.tray_menu.addAction("显示")
        self.show_action.triggered.connect(self.show_window)
        self.exit_action = self.tray_menu.addAction("退出")
        self.exit_action.triggered.connect(self.exit_application)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)

        self._tray_tip_shown = False
        self._restore_window_position()
        QtWidgets.QApplication.instance().aboutToQuit.connect(self._save_window_position)

    def _apply_theme(self):
        """应用深色科技风主题，统一卡片、控件、交互状态和提示的视觉层次。"""
        theme = """
            QWidget { color: #DCE7F5; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; }
            QWidget#keeperWindow { background: #0B1220; }
            QLabel { background: transparent; }
            QLabel#title { font-size: 25px; font-weight: bold; color: #F1F7FF; }
            QLabel#badge { color: #55D5E7; font-size: 10px; letter-spacing: 1px; }
            QFrame#card { background: #131F31; border: 1px solid #26364D; border-radius: 12px; }
            QLabel#sectionTitle { color: #68D8EC; font-size: 14px; font-weight: bold; }
            QLabel#muted { color: #8D9FB8; font-size: 12px; }
            QLineEdit, QSpinBox, QTimeEdit { background: #0D1727; border: 1px solid #32465F; border-radius: 7px; padding: 5px 10px; color: #ECF5FF; selection-background-color: #177E9B; }
            QLineEdit:focus, QSpinBox:focus, QTimeEdit:focus { border-color: #42C9E2; }
            QLineEdit:disabled, QSpinBox:disabled, QTimeEdit:disabled { color: #71849D; border-color: #26364D; background: #111B2A; }
            QSpinBox::up-button, QTimeEdit::up-button { width: 20px; border-left: 1px solid #32465F; background: #25364D; border-top-right-radius: 6px; }
            QSpinBox::down-button, QTimeEdit::down-button { width: 20px; border-left: 1px solid #32465F; background: #25364D; border-bottom-right-radius: 6px; }
            QSpinBox::up-arrow, QTimeEdit::up-arrow { image: url(UP_ICON); width: 10px; height: 10px; }
            QSpinBox::down-arrow, QTimeEdit::down-arrow { image: url(DOWN_ICON); width: 10px; height: 10px; }
            QCheckBox { spacing: 9px; background: transparent; }
            QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #4C637D; border-radius: 4px; background: #0D1727; }
            QCheckBox::indicator:checked { background: #36BCD6; border-color: #68E0EE; }
            QCheckBox#dayCheck { padding: 9px 8px; border: 1px solid #32465F; border-radius: 6px; color: #96ABC3; spacing: 0px; }
            QCheckBox#dayCheck::indicator { width: 0px; height: 0px; border: none; }
            QCheckBox#dayCheck:checked { background: #163A4B; border-color: #338EA5; color: #A3EEFA; }
            QCheckBox#dayCheck:disabled { color: #63768C; border-color: #26364D; }
            QLabel#helpIcon { border: 1px solid #4B7C96; border-radius: 10px; color: #8CDFF0; background: #193447; font-weight: bold; }
            QPushButton { background: #1C3047; color: #DCEBFA; border: 1px solid #36516D; border-radius: 8px; font-weight: bold; padding: 7px 14px; }
            QPushButton:hover { background: #29445F; border-color: #6ABBD1; }
            QPushButton:pressed { background: #15283D; }
            QPushButton#primaryButton { background: #21B6D1; color: #071A27; border-color: #52D9E8; }
            QPushButton#primaryButton:hover { background: #52D3E5; }
            QPushButton#stopButton:enabled { background: #482B3A; border-color: #9B536A; color: #FFC2D2; }
            QPushButton:disabled, QPushButton#primaryButton:disabled { background: #162235; color: #586D86; border-color: #26364D; }
            QLabel#statusLabel { background: #101E2E; border: 1px solid #244157; border-radius: 8px; padding: 10px; color: #8FD9E7; font-size: 12px; }
            QToolTip { background: #192B40; color: #E5F4FF; border: 1px solid #4F8FA5; padding: 10px; }
            QMenu { background: #162337; border: 1px solid #36516D; }
            QMenu::item { padding: 8px 22px; }
            QMenu::item:selected { background: #255168; }
        """
        theme = theme.replace("UP_ICON", resource_path("assets/chevron-up.svg").replace("\\", "/"))
        theme = theme.replace("DOWN_ICON", resource_path("assets/chevron-down.svg").replace("\\", "/"))
        self.setStyleSheet(theme)

    def _create_card(self):
        """创建统一留白的设置卡片，供各功能区组织控件。"""
        card = QtWidgets.QFrame(self)
        card.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        return card, layout

    def _create_help_icon(self, text):
        """创建布局中的圆圈问号，仅鼠标悬停在图标上时展示说明。"""
        icon = QtWidgets.QLabel('?', self)
        icon.setObjectName("helpIcon")
        icon.setFixedSize(20, 20)
        icon.setAlignment(QtCore.Qt.AlignCenter)
        icon.setCursor(QtCore.Qt.WhatsThisCursor)
        icon.setToolTip(text)
        return icon

    def _startup_command(self):
        """生成登录启动命令，兼容打包后的 EXE 和直接运行的源码，并正确引用带空格的路径。"""
        if getattr(sys, "frozen", False):
            return '"' + sys.executable + '"'
        python_path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.isfile(python_path):
            python_path = sys.executable
        return '"' + python_path + '" "' + os.path.abspath(__file__) + '"'

    def _login_startup_enabled(self):
        """读取当前用户实际的登录启动项，避免复制 INI 后误显示为已启用。"""
        if not IS_WINDOWS:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                command, _ = winreg.QueryValueEx(key, "ComputerKeeper")
                return command == self._startup_command()
        except FileNotFoundError:
            return False

    def _save_login_startup(self):
        """根据复选框添加或删除当前用户的登录启动项，无需管理员权限，仅在保存时执行。"""
        if not IS_WINDOWS:
            return
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            if self.startupCheck.isChecked():
                winreg.SetValueEx(key, "ComputerKeeper", 0, winreg.REG_SZ, self._startup_command())
            else:
                try:
                    winreg.DeleteValue(key, "ComputerKeeper")
                except FileNotFoundError:
                    pass

    def _restore_window_position(self):
        """恢复上次正常退出或隐藏时的窗口位置；首次打开时在当前屏幕居中显示。"""
        settings = QtCore.QSettings("ComputerKeeper", "Window")
        geometry = settings.value("geometry", QtCore.QByteArray(), type=QtCore.QByteArray)
        if geometry and self.restoreGeometry(geometry):
            return
        frame = self.frameGeometry()
        frame.moveCenter(self.screen().availableGeometry().center())
        self.move(frame.topLeft())

    def _save_window_position(self):
        """单独记录窗口位置，不创建或修改由保存按钮管理的时间 INI 文件。"""
        settings = QtCore.QSettings("ComputerKeeper", "Window")
        settings.setValue("geometry", self.saveGeometry())
        settings.sync()

    def _load_settings(self):
        """读取程序同目录的全部界面设置；缺失或无效的项保留默认值，不创建文件。"""
        self.startupCheck.setChecked(self._login_startup_enabled())
        if not os.path.isfile(self.settings_path):
            return
        settings = QtCore.QSettings(self.settings_path, QtCore.QSettings.IniFormat)
        settings.setFallbacksEnabled(False)
        for key, editor in self._time_editors().items():
            saved_time = QtCore.QTime.fromString(settings.value("time/" + key, "", type=str), "HH:mm")
            if saved_time.isValid():
                editor.setTime(saved_time)
        interval = settings.value("activity/interval_seconds", "30", type=str)
        if interval.isdecimal() and 1 <= int(interval) <= 86400:
            self.intervalLineEdit.setText(str(int(interval)))
        idle_minutes = settings.value("activity/idle_minutes", "5", type=str)
        if idle_minutes.isdecimal() and 1 <= int(idle_minutes) <= 240:
            self.idleMinutesSpin.setValue(int(idle_minutes))
        for day, checkbox in enumerate(self.dayChecks, start=1):
            checkbox.setChecked(settings.value("weekdays/day_" + str(day), checkbox.isChecked(), type=bool))

    def _time_editors(self):
        """返回配置键与时间控件的对应关系，统一读取和保存的字段。"""
        return {
            "start_time": self.startTimeEdit,
            "end_time": self.endTimeEdit,
            "lunch_start": self.lunchStartEdit,
            "lunch_end": self.lunchEndEdit,
        }

    def save_settings(self):
        """保存全部界面设置到程序同目录的 ComputerKeeper.ini，并更新当前用户的登录启动项。

        仅由“保存”按钮触发，不改变本次运行状态。立即同步到磁盘，写入失败时
        提示用户检查目录写入权限；启动、开始、停止和退出均不会自动保存配置。
        """
        if not self.intervalLineEdit.hasAcceptableInput():
            QtWidgets.QMessageBox.warning(self, '保存失败', '间隔时间请输入 1 到 86400 之间的整数。')
            return
        settings = QtCore.QSettings(self.settings_path, QtCore.QSettings.IniFormat)
        settings.setFallbacksEnabled(False)
        for key, editor in self._time_editors().items():
            settings.setValue("time/" + key, editor.time().toString("HH:mm"))
        settings.setValue("activity/interval_seconds", int(self.intervalLineEdit.text()))
        settings.setValue("activity/idle_minutes", self.idleMinutesSpin.value())
        settings.setValue("startup/enabled", self.startupCheck.isChecked())
        for day, checkbox in enumerate(self.dayChecks, start=1):
            settings.setValue("weekdays/day_" + str(day), checkbox.isChecked())
        settings.sync()
        if settings.status() != QtCore.QSettings.NoError:
            QtWidgets.QMessageBox.warning(self, '保存失败', '无法写入配置文件，请检查程序目录的写入权限。\n' + self.settings_path)
            return
        try:
            self._save_login_startup()
        except OSError as error:
            QtWidgets.QMessageBox.warning(self, '登录启动设置失败', '配置文件已保存，但无法更新登录启动项：\n' + str(error))
            return
        startup_message = '已启用开机自启。' if self.startupCheck.isChecked() else '已关闭开机自启。'
        QtWidgets.QMessageBox.information(self, '保存成功', '设置已保存，点击“开始”使用当前设置，下次启动自动恢复。\n' + startup_message + '\n' + self.settings_path)

    # ------------------ UI 控制 ------------------
    def start_moving(self):
        text = self.intervalLineEdit.text().strip()
        if not text:
            QtWidgets.QMessageBox.warning(self, '输入错误', '请输入间隔秒数（数字）')
            return
        try:
            interval = int(text)
            if interval <= 0:
                raise ValueError
        except ValueError:
            QtWidgets.QMessageBox.warning(self, '输入错误', '间隔时间仅可填写数字（> 0）')
            return

        # 读取设置
        self.start_time = self.startTimeEdit.time()
        self.end_time = self.endTimeEdit.time()
        self.lunch_start = self.lunchStartEdit.time()
        self.lunch_end = self.lunchEndEdit.time()
        self.idle_minutes_threshold = max(1, int(self.idleMinutesSpin.value()))
        self.interval_seconds = interval

        # 校验1：开始时间不能大于结束时间（不支持跨午夜）
        if self.start_time > self.end_time:
            QtWidgets.QMessageBox.warning(self, '时间设置错误', '开始时间不能大于结束时间（不支持跨午夜）。')
            return

        # 校验2：开始-结束时长 ≥ 10 分钟 且 ≥ 空闲触发时间
        duration_secs = self.start_time.secsTo(self.end_time)  # 已保证非负
        if duration_secs < 600:
            QtWidgets.QMessageBox.warning(self, '时间设置错误', '开始时间到结束时间的时长不能小于 10 分钟。')
            return
        if duration_secs < self.idle_minutes_threshold * 60:
            QtWidgets.QMessageBox.warning(self, '时间设置错误', '开始-结束时长不能小于空闲触发时间。')
            return

        # 记录“当天有效”模式
        self.no_day_selected = not any(cb.isChecked() for cb in self.dayChecks)
        self.anchor_date = datetime.date.today() if self.no_day_selected else None

        # 若“当天有效”且当前已过结束时间，则不启动
        if self.no_day_selected and self._is_session_finished_for_no_day_selected():
            self.running = False
            self.active_mode = False
            self.statusLabel.setText("状态：当天结束时间已到，未开始（请明天或重新设置后再开始）")
            return

        # 进入运行
        self.running = True
        self.active_mode = False

        # UI 状态
        self.startButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self.intervalLineEdit.setEnabled(False)
        self.startTimeEdit.setEnabled(False)
        self.endTimeEdit.setEnabled(False)
        self.lunchStartEdit.setEnabled(False)
        self.lunchEndEdit.setEnabled(False)
        for cb in self.dayChecks:
            cb.setEnabled(False)
        self.idleMinutesSpin.setEnabled(False)
        self.statusLabel.setText(self._waiting_status_text())

        if not self._tray_tip_shown:
            try:
                self.tray_icon.showMessage(
                    "ComputerKeeper",
                    "程序已在后台运行：达到设置的时间窗与（若选择）日期，并在空闲达阈值后自动执行。\n午休时段暂停执行（非结束）。\n未选择星期时：当天结束时间到后自动停止，需要手动重新开始。",
                    QtWidgets.QSystemTrayIcon.Information,
                    6000
                )
                self._tray_tip_shown = True
            except Exception:
                pass

        self._schedule_next()

    def stop_moving(self):
        if not self.running and not self.active_mode:
            return
        self.running = False
        self.active_mode = False
        self.timer.stop()
        disable_keep_awake()

        self.startButton.setEnabled(True)
        self.stopButton.setEnabled(False)
        self.intervalLineEdit.setEnabled(True)
        self.startTimeEdit.setEnabled(True)
        self.endTimeEdit.setEnabled(True)
        self.lunchStartEdit.setEnabled(True)
        self.lunchEndEdit.setEnabled(True)
        for cb in self.dayChecks:
            cb.setEnabled(True)
        self.idleMinutesSpin.setEnabled(True)
        self.statusLabel.setText("状态：已停止")

    # ------------------ 时间/日期判断 ------------------
    def _is_day_allowed(self, dt: datetime.datetime) -> bool:
        if self.no_day_selected:
            return dt.date() == self.anchor_date
        wd = dt.weekday()  # 周一=0, 周日=6
        return self.dayChecks[wd].isChecked()

    def _is_in_time_window_now(self) -> bool:
        # 不支持跨午夜：开始 <= 结束
        now = datetime.datetime.now()
        now_time = QtCore.QTime.currentTime()
        start_t = self.start_time
        end_t = self.end_time
        in_window = (now_time >= start_t and now_time < end_t)
        return in_window and self._is_day_allowed(now)

    def _is_in_lunch_break_now(self) -> bool:
        s = self.lunch_start
        e = self.lunch_end
        if s == e:
            return False
        now_t = QtCore.QTime.currentTime()
        if s <= e:
            return s <= now_t < e
        else:
            # 允许设置跨午夜午休，但一般不需要
            return (now_t >= s) or (now_t < e)

    def _is_session_finished_for_no_day_selected(self) -> bool:
        # 当天有效：当天到点即结束；不考虑跨午夜（已禁止）
        if not self.no_day_selected or self.anchor_date is None:
            return False
        now = datetime.datetime.now()
        today = now.date()
        now_t = QtCore.QTime.currentTime()
        if today > self.anchor_date:
            return True
        if today == self.anchor_date and now_t >= self.end_time:
            return True
        return False

    # ------------------ 定时与逻辑 ------------------
    def _schedule_next(self):
        if not self.running:
            return
        if self.no_day_selected and self._is_session_finished_for_no_day_selected():
            self.timer.stop()
            return
        if not self._is_in_time_window_now():
            delay_ms = 60000
        elif self._is_in_lunch_break_now():
            delay_ms = 60000
        elif not self.active_mode:
            delay_ms = 15000
        else:
            base = max(self.interval_seconds, 3)
            factor = random.uniform(0.7, 1.3)
            delay_ms = int(base * factor * 1000)
        self.timer.start(delay_ms)

    def _on_timer(self):
        if not self.running:
            return

        if self.no_day_selected and self._is_session_finished_for_no_day_selected():
            self.stop_moving()
            self.statusLabel.setText("状态：当天结束时间已到，已停止（请重新开始）")
            return

        if not self._is_in_time_window_now():
            if self.active_mode:
                self.active_mode = False
                disable_keep_awake()
            self.statusLabel.setText(self._waiting_status_text())
            self._schedule_next()
            return

        if self._is_in_lunch_break_now():
            if self.active_mode:
                self.active_mode = False
                disable_keep_awake()
            self.statusLabel.setText("状态：午休中（暂停执行）")
            self._schedule_next()
            return

        if not self.active_mode:
            idle_secs = self._get_idle_seconds()
            if idle_secs >= self.idle_minutes_threshold * 60:
                self.active_mode = True
                enable_keep_awake()
                self.statusLabel.setText("状态：运行中（空闲触发）")
                self._poke_once()
            else:
                left = max(0, self.idle_minutes_threshold * 60 - int(idle_secs))
                self.statusLabel.setText(f"状态：待机（在时间窗内，距空闲触发还需约 {left} 秒）")
        else:
            self._poke_once()

        self._schedule_next()

    def _waiting_status_text(self) -> str:
        start_str = self.start_time.toString("HH:mm")
        end_str = self.end_time.toString("HH:mm")
        lunch_str = f"{self.lunch_start.toString('HH:mm')}~{self.lunch_end.toString('HH:mm')}"
        day_names = ["周一","周二","周三","周四","周五","周六","周日"]
        selected = [name for i, name in enumerate(day_names) if self.dayChecks[i].isChecked()]
        if self.no_day_selected:
            day_str = "当天"
        else:
            day_str = "、".join(selected) if selected else "未选择日期"
        return f"状态：待机（等待 {day_str} 的 {start_str}~{end_str} 时间窗，午休 {lunch_str} 暂停）"

    def _poke_once(self):
        r = random.random()
        try:
            if IS_WINDOWS:
                if r < 0.5:
                    user32.mouse_event(MOUSEEVENTF_MOVE, 1, 1, 0, 0)
                    user32.mouse_event(MOUSEEVENTF_MOVE, -1, -1, 0, 0)
                elif r < 0.8:
                    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, 120, 0)
                    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, -120, 0)
                else:
                    user32.keybd_event(VK_SHIFT, 0, 0, 0)
                    user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
            else:
                pos = QtGui.QCursor.pos()
                QtGui.QCursor.setPos(pos.x() + 1, pos.y() + 1)
                QtGui.QCursor.setPos(pos)
        except Exception:
            pos = QtGui.QCursor.pos()
            QtGui.QCursor.setPos(pos.x() + 1, pos.y() + 1)
            QtGui.QCursor.setPos(pos)

    # ------------------ 空闲检测 ------------------
    def _get_idle_seconds(self):
        if IS_WINDOWS and self.use_raw_input:
            return max(0.0, time.monotonic() - self.last_user_input_ts)
        elif IS_WINDOWS:
            return get_idle_seconds_win32()
        else:
            return 999999.0

    def _on_user_activity(self):
        self.last_user_input_ts = time.monotonic()
        if self.running and self.active_mode:
            self.active_mode = False
            disable_keep_awake()
            self.statusLabel.setText("状态：用户活动，已暂停（等待再次空闲）")
            self.timer.stop()
            self.timer.start(5000)

    # ------------------ Raw Input ------------------
    def _register_raw_input(self):
        if not IS_WINDOWS:
            return False
        try:
            hwnd = int(self.winId())
            devices = (RAWINPUTDEVICE * 2)()
            devices[0].usUsagePage = 0x01
            devices[0].usUsage = 0x02
            devices[0].dwFlags = RIDEV_INPUTSINK
            devices[0].hwndTarget = hwnd
            devices[1].usUsagePage = 0x01
            devices[1].usUsage = 0x06
            devices[1].dwFlags = RIDEV_INPUTSINK
            devices[1].hwndTarget = hwnd
            if not user32.RegisterRawInputDevices(ctypes.byref(devices), 2, ctypes.sizeof(RAWINPUTDEVICE)):
                return False
            return True
        except Exception:
            return False

    def nativeEvent(self, eventType, message):
        if IS_WINDOWS and eventType == "windows_generic_MSG":
            msg = MSG.from_address(int(message))
            if msg.message == WM_INPUT:
                size = wintypes.UINT(0)
                user32.GetRawInputData(msg.lParam, RID_HEADER, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
                if size.value:
                    buf = ctypes.create_string_buffer(size.value)
                    if user32.GetRawInputData(msg.lParam, RID_HEADER, buf, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER)) == size.value:
                        header = RAWINPUTHEADER.from_buffer_copy(buf)
                        if header.dwType in (RIM_TYPEMOUSE, RIM_TYPEKEYBOARD):
                            self._on_user_activity()
        return False, 0

    # ------------------ 窗口与托盘 ------------------
    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if not self._tray_tip_shown:
            try:
                self.tray_icon.showMessage(
                    "ComputerKeeper",
                    "程序已最小化到托盘，仍会在后台按设置运行（午休时间暂停）。\n右击托盘图标可退出。",
                    QtWidgets.QSystemTrayIcon.Information,
                    6000
                )
                self._tray_tip_shown = True
            except Exception:
                pass

    def showEvent(self, event):
        if IS_WINDOWS and not self.raw_input_registered:
            self.raw_input_registered = True
            ok = self._register_raw_input()
            self.use_raw_input = ok
            self.last_user_input_ts = time.monotonic()
        self.tray_icon.setVisible(True)
        event.accept()

    def hideEvent(self, event):
        """隐藏到托盘时记录窗口位置，保持再次显示和下次启动的位置一致。"""
        self._save_window_position()
        self.tray_icon.setVisible(True)
        event.accept()

    def tray_icon_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def exit_application(self):
        self.stop_moving()
        QtWidgets.QApplication.quit()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    # 设置应用图标（任务栏等处）
    app.setWindowIcon(QtGui.QIcon(resource_path("icon.png")))
    window = MouseMover()
    window.show()
    sys.exit(app.exec_())

