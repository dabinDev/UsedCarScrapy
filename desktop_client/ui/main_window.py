from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QFrame,
    QScrollArea,
    QSplitter,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from desktop_client.models import STAGES_BY_SOURCE, DatabaseConfig, SelectionItem, TaskScope
from desktop_client.runtime.db_runtime import test_db_connection
from desktop_client.runtime.dongchedi_runner import DongchediRunner
from desktop_client.runtime.source_defaults import build_default_task_config, default_db_config
from desktop_client.runtime.status import build_scope_progress, build_workspace_summary, format_workspace_summary
from desktop_client.runtime.workspace import WorkspaceManager
from desktop_client.ui.form_mapping import build_task_config, parse_text_list


STATE_COLORS = {
    "pending": QColor("#334155"),
    "series_loaded": QColor("#d97706"),
    "overview_done": QColor("#d97706"),
    "detail_done": QColor("#15803d"),
    "running": QColor("#2563eb"),
}

STATE_BACKGROUNDS = {
    "pending": QColor("#ffffff"),
    "series_loaded": QColor("#fff7ed"),
    "overview_done": QColor("#fff7ed"),
    "detail_done": QColor("#f0fdf4"),
    "running": QColor("#eff6ff"),
}


class BackgroundTaskSignals(QObject):
    result_ready = Signal(object)
    error_raised = Signal(str)
    finished = Signal()


class BackgroundTaskRunnable(QRunnable):
    def __init__(self, target):
        super().__init__()
        self._target = target
        self.signals = BackgroundTaskSignals()

    def run(self) -> None:
        try:
            result = self._target()
        except Exception:
            self.signals.error_raised.emit(traceback.format_exc())
        else:
            self.signals.result_ready.emit(result)
        finally:
            self.signals.finished.emit()


class MainWindow(QMainWindow):
    runtime_event = Signal(str, str)

    def __init__(self, workspace_root: Path):
        super().__init__()
        self.workspace_manager = WorkspaceManager(workspace_root)
        self.dongchedi_runner = DongchediRunner(self.workspace_manager, event_callback=self._emit_runtime_event)
        self.current_workspace = None
        self.selected_brands: list[SelectionItem] = []
        self.selected_series: list[SelectionItem] = []
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(10)
        self._task_worker: BackgroundTaskRunnable | None = None
        self._active_task_title = ""
        self._scope_refresh_timer = QTimer(self)
        self._scope_refresh_timer.setSingleShot(True)
        self._scope_refresh_timer.setInterval(180)
        self._scope_refresh_timer.timeout.connect(self._refresh_scope_progress_visuals)

        self.runtime_event.connect(self._handle_runtime_event)

        self.setWindowTitle("车源采集桌面客户端")
        self.resize(1420, 840)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(self._build_header())
        layout.addWidget(self._build_body(), 1)
        self.setCentralWidget(container)

        self._apply_visual_style()
        self.max_workers_input.valueChanged.connect(lambda _: self._refresh_header_badges())
        self.resume_policy_combo.currentIndexChanged.connect(lambda _: self._refresh_header_badges())
        self.show_browser_checkbox.toggled.connect(lambda _: self._refresh_header_badges())
        self.enable_db_checkbox.toggled.connect(lambda _: self._refresh_header_badges())
        self._apply_source_defaults("dongchedi", announce=False)
        self._sync_source_specific_sections()
        self._sync_db_group_state()
        self._sync_action_state()
        self._refresh_header_badges()
        self._refresh_dashboard_cards()
        self._set_status("准备就绪，可先调整配置后创建工作区。")

    def _build_button(
        self,
        text: str,
        *,
        variant: str = "primary",
        compact: bool = False,
        slot=None,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("variant", variant)
        button.setProperty("compact", compact)
        button.setMinimumHeight(32 if compact else 38)
        if slot is not None:
            button.clicked.connect(slot)
        return button

    def _build_badge(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "heroChip")
        label.setAlignment(Qt.AlignCenter)
        return label

    def _build_metric_card(self, title: str, note: str) -> tuple[QFrame, QLabel, QLabel]:
        frame = QFrame()
        frame.setProperty("cardStyle", "metric")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setProperty("role", "metricTitle")
        value_label = QLabel("--")
        value_label.setProperty("role", "metricValue")
        value_label.setWordWrap(True)
        note_label = QLabel(note)
        note_label.setProperty("role", "metricNote")
        note_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(note_label)
        return frame, value_label, note_label

    def _build_header(self) -> QWidget:
        widget = QFrame()
        widget.setObjectName("heroCard")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        eyebrow = QLabel("DESKTOP CONTROL CENTER")
        eyebrow.setProperty("role", "heroEyebrow")
        title = QLabel("车源采集桌面客户端")
        title.setProperty("role", "heroTitle")
        subtitle = QLabel("保持原脚本语义，补齐配置映射、工作区迁移和断点续采操作。")
        subtitle.setProperty("role", "heroSubtitle")
        subtitle.setWordWrap(True)
        title_layout.addWidget(eyebrow)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        badge_layout = QHBoxLayout()
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setSpacing(8)
        self.source_badge = self._build_badge("数据源")
        self.thread_badge = self._build_badge("并发")
        self.resume_badge = self._build_badge("续采")
        self.browser_badge = self._build_badge("浏览器")
        for badge in (self.source_badge, self.thread_badge, self.resume_badge, self.browser_badge):
            badge_layout.addWidget(badge)
        self.load_defaults_button = self._build_button(
            "载入原脚本默认配置",
            variant="secondary",
            slot=self._load_current_source_defaults,
        )

        layout.addLayout(title_layout, 1)
        right_layout.addLayout(badge_layout)
        right_layout.addWidget(self.load_defaults_button, 0, Qt.AlignRight)
        layout.addLayout(right_layout, 0)
        return widget

    def _build_body(self) -> QWidget:
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([860, 620])

        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._build_dashboard_strip())
        layout.addWidget(splitter, 1)
        return wrapper

    def _build_dashboard_strip(self) -> QWidget:
        widget = QFrame()
        widget.setObjectName("dashboardStrip")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        workspace_card, self.workspace_metric_value, self.workspace_metric_note = self._build_metric_card(
            "工作区",
            "创建或导入后可跨机器继续抓取",
        )
        scope_card, self.scope_metric_value, self.scope_metric_note = self._build_metric_card(
            "抓取范围",
            "品牌、车系、城市会和断点一起持久化",
        )
        task_card, self.task_metric_value, self.task_metric_note = self._build_metric_card(
            "当前任务",
            "等待下一步操作",
        )
        result_card, self.result_metric_value, self.result_metric_note = self._build_metric_card(
            "结果快照",
            "概览、详情和目录计数会实时同步",
        )

        for card in (workspace_card, scope_card, task_card, result_card):
            layout.addWidget(card, 1)
        return widget

    def _apply_visual_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #edf3f8;
            }
            QLabel {
                color: #1f2937;
            }
            QFrame#heroCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0f172a,
                    stop: 0.55 #17365d,
                    stop: 1 #1d4ed8
                );
                border: 1px solid rgba(191, 219, 254, 0.28);
                border-radius: 24px;
            }
            QLabel[role="heroEyebrow"] {
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLabel[role="heroTitle"] {
                color: #f8fafc;
                font-size: 24px;
                font-weight: 800;
            }
            QLabel[role="heroSubtitle"] {
                color: rgba(241, 245, 249, 0.92);
                font-size: 12px;
            }
            QLabel[role="heroChip"] {
                background: rgba(255, 255, 255, 0.12);
                color: #eff6ff;
                border: 1px solid rgba(219, 234, 254, 0.24);
                border-radius: 14px;
                padding: 4px 9px;
                font-weight: 700;
                min-width: 72px;
            }
            QFrame[cardStyle="metric"] {
                background: #ffffff;
                border: 1px solid #dce6f1;
                border-radius: 18px;
            }
            QLabel[role="metricTitle"] {
                color: #64748b;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel[role="metricValue"] {
                color: #0f172a;
                font-size: 16px;
                font-weight: 800;
            }
            QLabel[role="metricNote"] {
                color: #6b7280;
                font-size: 11px;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d6e0ed;
                border-radius: 18px;
                margin-top: 14px;
                padding-top: 18px;
                font-weight: 700;
                color: #1e293b;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
            }
            QLineEdit, QPlainTextEdit, QListWidget, QComboBox, QSpinBox {
                background: #fbfdff;
                border: 1px solid #d7e1eb;
                border-radius: 12px;
                padding: 8px 10px;
                selection-background-color: #bfdbfe;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QListWidget:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #60a5fa;
            }
            QScrollArea {
                background: transparent;
                border: 0;
            }
            QListWidget {
                padding: 4px;
            }
            QListWidget::item {
                border-radius: 10px;
                padding: 6px 8px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background: #dbeafe;
                color: #1d4ed8;
            }
            QPushButton {
                color: #ffffff;
                border: 0;
                border-radius: 12px;
                padding: 7px 12px;
                font-weight: 700;
            }
            QPushButton[variant="primary"] {
                background: #2563eb;
            }
            QPushButton[variant="primary"]:hover {
                background: #1d4ed8;
            }
            QPushButton[variant="secondary"] {
                background: #e2e8f0;
                color: #0f172a;
            }
            QPushButton[variant="secondary"]:hover {
                background: #cbd5e1;
            }
            QPushButton[variant="ghost"] {
                background: #f8fafc;
                color: #334155;
                border: 1px solid #cbd5e1;
            }
            QPushButton[variant="ghost"]:hover {
                background: #eef2f7;
            }
            QPushButton[variant="success"] {
                background: #0f766e;
            }
            QPushButton[variant="success"]:hover {
                background: #0d9488;
            }
            QPushButton:disabled {
                background: #cbd5e1;
                color: #f8fafc;
            }
            QPushButton[compact="true"] {
                padding: 6px 10px;
            }
            QCheckBox {
                spacing: 8px;
                color: #334155;
            }
            QProgressBar {
                background: #dbe4ef;
                border: 0;
                border-radius: 8px;
                min-height: 12px;
            }
            QProgressBar::chunk {
                background: #2563eb;
                border-radius: 8px;
            }
            QSplitter::handle {
                background: transparent;
            }
            QSplitter::handle:horizontal {
                width: 10px;
            }
            QSplitter::handle:vertical {
                height: 10px;
            }
            QPlainTextEdit#workspaceInfoPane {
                background: #f8fafc;
                color: #0f172a;
            }
            QPlainTextEdit#logPane {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #1e293b;
            }
            """
        )

    def _build_left_panel(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self._build_basic_group())
        layout.addWidget(self._build_database_group())
        layout.addWidget(self._build_scope_group())
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _build_right_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        control_stack = QWidget()
        control_layout = QVBoxLayout(control_stack)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(10)
        control_layout.addWidget(self._build_workspace_ops_group())
        control_layout.addWidget(self._build_capture_ops_group())

        feedback_splitter = QSplitter(Qt.Vertical)
        feedback_splitter.addWidget(self._build_status_group())
        feedback_splitter.addWidget(self._build_log_group())
        feedback_splitter.setStretchFactor(0, 4)
        feedback_splitter.setStretchFactor(1, 5)
        feedback_splitter.setSizes([260, 380])

        layout.addWidget(control_stack)
        layout.addWidget(feedback_splitter, 1)
        return widget

    def _build_basic_group(self) -> QGroupBox:
        group = QGroupBox("基础配置")
        layout = QFormLayout(group)
        layout.setSpacing(10)

        self.task_name_input = QLineEdit()
        self.source_combo = QComboBox()
        self.source_combo.addItems(["dongchedi", "guazi"])
        self.source_combo.currentTextChanged.connect(self._on_source_changed)

        output_layout = QHBoxLayout()
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("例如：client_output")
        self.output_dir_button = self._build_button("选择目录", variant="secondary", compact=True, slot=self._choose_output_dir)
        output_layout.addWidget(self.output_dir_input, 1)
        output_layout.addWidget(self.output_dir_button)

        self.max_workers_input = QSpinBox()
        self.max_workers_input.setRange(1, 64)
        self.max_pages_input = QSpinBox()
        self.max_pages_input.setRange(1, 9999)

        self.resume_policy_combo = QComboBox()
        self.resume_policy_combo.addItem("继续已有进度", "resume")
        self.resume_policy_combo.addItem("清空旧结果后重跑", "restart")

        self.show_browser_checkbox = QCheckBox("显示浏览器窗口")
        self.enable_ocr_checkbox = QCheckBox("采集概览时保存截图并启用 OCR")
        self.enable_db_checkbox = QCheckBox("同步到 MySQL 数据库")
        self.enable_db_checkbox.toggled.connect(self._sync_db_group_state)

        layout.addRow("任务名称", self.task_name_input)
        layout.addRow("数据源", self.source_combo)
        layout.addRow("输出目录", output_layout)
        layout.addRow("并发线程", self.max_workers_input)
        layout.addRow("最大页数", self.max_pages_input)
        layout.addRow("已有进度处理", self.resume_policy_combo)
        layout.addRow("", self.show_browser_checkbox)
        layout.addRow("", self.enable_ocr_checkbox)
        layout.addRow("", self.enable_db_checkbox)
        return group

    def _build_database_group(self) -> QGroupBox:
        self.database_group = QGroupBox("数据库配置")
        layout = QFormLayout(self.database_group)
        layout.setSpacing(10)

        self.db_host_input = QLineEdit()
        self.db_port_input = QSpinBox()
        self.db_port_input.setRange(1, 65535)
        self.db_user_input = QLineEdit()
        self.db_password_input = QLineEdit()
        self.db_password_input.setEchoMode(QLineEdit.Password)
        self.db_database_input = QLineEdit()
        self.db_charset_input = QLineEdit()

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        self.load_db_defaults_button = self._build_button(
            "回填 db_config 默认值",
            variant="secondary",
            compact=True,
            slot=self._load_db_defaults,
        )
        self.test_db_button = self._build_button("测试连接", variant="primary", compact=True, slot=self._test_database_connection)
        button_layout.addWidget(self.load_db_defaults_button)
        button_layout.addWidget(self.test_db_button)
        button_layout.addStretch(1)

        layout.addRow("主机", self.db_host_input)
        layout.addRow("端口", self.db_port_input)
        layout.addRow("用户名", self.db_user_input)
        layout.addRow("密码", self.db_password_input)
        layout.addRow("数据库", self.db_database_input)
        layout.addRow("字符集", self.db_charset_input)
        layout.addRow("", button_layout)
        return self.database_group

    def _build_scope_group(self) -> QGroupBox:
        group = QGroupBox("抓取范围")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        self.scope_hint_label = QLabel("懂车帝支持品牌和车系多选，瓜子保留城市范围配置。")
        self.scope_hint_label.setWordWrap(True)
        self.scope_hint_label.setStyleSheet("color: #64748b;")
        layout.addWidget(self.scope_hint_label)

        self.city_group = QGroupBox("城市范围")
        city_layout = QVBoxLayout(self.city_group)
        self.cities_input = QPlainTextEdit()
        self.cities_input.setPlaceholderText("每行一个城市编码，或使用逗号分隔，例如：bj,sh,gz")
        self.cities_input.setFixedHeight(90)
        city_layout.addWidget(self.cities_input)
        layout.addWidget(self.city_group)

        self.dongchedi_scope_group = QGroupBox("品牌与车系")
        dongchedi_layout = QVBoxLayout(self.dongchedi_scope_group)
        dongchedi_layout.setSpacing(10)

        brand_group = QGroupBox("品牌选择")
        brand_layout = QGridLayout(brand_group)
        brand_layout.setSpacing(8)
        self.brand_catalog_list = QListWidget()
        self.brand_catalog_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.brand_catalog_list.setMinimumHeight(180)
        self.brand_catalog_list.itemSelectionChanged.connect(self._preview_brand_selection)
        self.brand_selection_view = QListWidget()
        self.brand_selection_view.setSelectionMode(QAbstractItemView.NoSelection)
        self.brand_selection_view.setFocusPolicy(Qt.NoFocus)
        self.brand_selection_view.setMinimumHeight(180)
        brand_toolbar = QHBoxLayout()
        brand_toolbar.setContentsMargins(0, 0, 0, 0)
        self.select_all_brands_button = self._build_button(
            "全部品牌",
            variant="secondary",
            compact=True,
            slot=lambda: self._select_all_in_list(
                self.brand_catalog_list,
                "已勾选当前品牌目录中的全部品牌，点击“保存当前品牌选择”即可落盘。",
            ),
        )
        self.clear_brand_selection_button = self._build_button(
            "清空品牌勾选",
            variant="ghost",
            compact=True,
            slot=lambda: self._clear_selection_in_list(
                self.brand_catalog_list,
                "已清空当前品牌勾选。",
            ),
        )
        brand_toolbar.addWidget(self.select_all_brands_button)
        brand_toolbar.addWidget(self.clear_brand_selection_button)
        brand_toolbar.addStretch(1)
        brand_layout.addWidget(QLabel("品牌目录"), 0, 0)
        brand_layout.addWidget(QLabel("已选品牌"), 0, 1)
        brand_layout.addLayout(brand_toolbar, 1, 0, 1, 2)
        brand_layout.addWidget(self.brand_catalog_list, 2, 0)
        brand_layout.addWidget(self.brand_selection_view, 2, 1)
        brand_layout.setColumnStretch(0, 1)
        brand_layout.setColumnStretch(1, 1)
        dongchedi_layout.addWidget(brand_group)

        series_group = QGroupBox("车系选择")
        series_layout = QGridLayout(series_group)
        series_layout.setSpacing(8)
        self.series_catalog_list = QListWidget()
        self.series_catalog_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.series_catalog_list.setMinimumHeight(220)
        self.series_catalog_list.itemSelectionChanged.connect(self._preview_series_selection)
        self.series_selection_view = QListWidget()
        self.series_selection_view.setSelectionMode(QAbstractItemView.NoSelection)
        self.series_selection_view.setFocusPolicy(Qt.NoFocus)
        self.series_selection_view.setMinimumHeight(220)
        series_toolbar = QHBoxLayout()
        series_toolbar.setContentsMargins(0, 0, 0, 0)
        self.select_all_series_button = self._build_button(
            "全部车系",
            variant="secondary",
            compact=True,
            slot=lambda: self._select_all_in_list(
                self.series_catalog_list,
                "已勾选当前品牌下的全部车系，点击“保存当前车系选择”即可一次性落盘。",
            ),
        )
        self.clear_series_selection_button = self._build_button(
            "清空车系勾选",
            variant="ghost",
            compact=True,
            slot=lambda: self._clear_selection_in_list(
                self.series_catalog_list,
                "已清空当前车系勾选。",
            ),
        )
        series_toolbar.addWidget(self.select_all_series_button)
        series_toolbar.addWidget(self.clear_series_selection_button)
        series_toolbar.addStretch(1)
        series_layout.addWidget(QLabel("车系列表"), 0, 0)
        series_layout.addWidget(QLabel("已选车系"), 0, 1)
        series_layout.addLayout(series_toolbar, 1, 0, 1, 2)
        series_layout.addWidget(self.series_catalog_list, 2, 0)
        series_layout.addWidget(self.series_selection_view, 2, 1)
        series_layout.setColumnStretch(0, 1)
        series_layout.setColumnStretch(1, 1)
        dongchedi_layout.addWidget(series_group)

        layout.addWidget(self.dongchedi_scope_group)
        return group

    def _build_workspace_ops_group(self) -> QGroupBox:
        group = QGroupBox("任务与工作区")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.workspace_path_view = QLineEdit()
        self.workspace_path_view.setReadOnly(True)
        self.workspace_path_view.setPlaceholderText("创建或导入工作区后显示当前路径")
        layout.addWidget(self.workspace_path_view)

        button_grid = QGridLayout()
        button_grid.setSpacing(8)

        self.create_workspace_button = self._build_button("创建或更新工作区", variant="success", slot=self._create_workspace)
        self.import_workspace_button = self._build_button("导入工作区 ZIP", variant="secondary", slot=self._import_workspace)
        self.export_workspace_button = self._build_button("导出工作区 ZIP", variant="ghost", slot=self._export_workspace)
        self.import_progress_button = self._build_button("导入断点 JSON", variant="secondary", slot=self._import_progress)
        self.export_progress_button = self._build_button("导出断点 JSON", variant="ghost", slot=self._export_progress)
        self.merge_workspace_button = self._build_button("合并工作区", variant="secondary", slot=self._merge_workspace)
        self.refresh_button = self._build_button("刷新摘要", variant="ghost", slot=self._refresh_workspace_summary)

        button_grid.addWidget(self.create_workspace_button, 0, 0)
        button_grid.addWidget(self.import_workspace_button, 0, 1)
        button_grid.addWidget(self.export_workspace_button, 0, 2)
        button_grid.addWidget(self.import_progress_button, 1, 0)
        button_grid.addWidget(self.export_progress_button, 1, 1)
        button_grid.addWidget(self.merge_workspace_button, 1, 2)
        button_grid.addWidget(self.refresh_button, 2, 0)
        layout.addLayout(button_grid)
        return group

    def _build_capture_ops_group(self) -> QGroupBox:
        group = QGroupBox("目录与抓取操作")
        layout = QGridLayout(group)
        layout.setSpacing(8)

        self.load_brand_catalog_button = self._build_button("1. 加载品牌目录", variant="primary", slot=self._load_brand_catalog)
        self.apply_brand_selection_button = self._build_button("2. 保存当前品牌选择", variant="secondary", slot=self._apply_brand_selection)
        self.load_series_catalog_button = self._build_button("3. 加载车系目录", variant="primary", slot=self._load_series_catalog)
        self.apply_series_selection_button = self._build_button("4. 保存当前车系选择", variant="secondary", slot=self._apply_series_selection)
        self.load_overviews_button = self._build_button("5. 抓取概览", variant="primary", slot=self._load_overviews)
        self.load_details_button = self._build_button("6. 抓取详情", variant="success", slot=self._load_details)

        layout.addWidget(self.load_brand_catalog_button, 0, 0)
        layout.addWidget(self.apply_brand_selection_button, 0, 1)
        layout.addWidget(self.load_series_catalog_button, 1, 0)
        layout.addWidget(self.apply_series_selection_button, 1, 1)
        layout.addWidget(self.load_overviews_button, 2, 0)
        layout.addWidget(self.load_details_button, 2, 1)
        return group

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("状态摘要")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.loading_title_label = QLabel("当前任务：空闲")
        self.loading_title_label.setStyleSheet("font-weight: 600;")
        self.loading_detail_label = QLabel("等待下一步操作。")
        self.loading_detail_label.setWordWrap(True)
        self.loading_detail_label.setStyleSheet("color: #666;")
        self.loading_progress = QProgressBar()
        self.loading_progress.setTextVisible(False)
        self.loading_progress.setRange(0, 1)
        self.loading_progress.setValue(0)
        self.loading_progress.hide()

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-weight: 600;")
        self.scope_legend_label = QLabel("颜色说明：黄色表示车系目录或概览已完成，绿色表示详情已完成。")
        self.scope_legend_label.setWordWrap(True)
        self.scope_legend_label.setStyleSheet("color: #475569;")
        status_callout = QFrame()
        status_callout.setProperty("cardStyle", "metric")
        status_callout_layout = QVBoxLayout(status_callout)
        status_callout_layout.setContentsMargins(14, 12, 14, 12)
        status_callout_layout.setSpacing(6)
        status_callout_layout.addWidget(self.loading_title_label)
        status_callout_layout.addWidget(self.loading_detail_label)
        status_callout_layout.addWidget(self.loading_progress)
        status_callout_layout.addWidget(self.status_label)
        status_callout_layout.addWidget(self.scope_legend_label)
        self.workspace_info = QPlainTextEdit()
        self.workspace_info.setObjectName("workspaceInfoPane")
        self.workspace_info.setReadOnly(True)
        self.workspace_info.setPlaceholderText("工作区摘要会显示在这里。")
        self.workspace_info.setMaximumHeight(220)
        layout.addWidget(status_callout)
        layout.addWidget(self.workspace_info, 1)
        return group

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("运行日志")
        layout = QVBoxLayout(group)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logPane")
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("目录加载、详情落盘和异常信息会实时显示在这里。")
        self.log_view.setMinimumHeight(240)
        layout.addWidget(self.log_view)
        return group

    def _on_source_changed(self, source: str) -> None:
        self._sync_source_specific_sections()
        self._sync_action_state()
        self._refresh_header_badges()
        self._refresh_dashboard_cards()
        self._set_status(f"当前数据源：{source}。")

    def _load_current_source_defaults(self) -> None:
        self._apply_source_defaults(self.source_combo.currentText(), announce=True)

    def _apply_source_defaults(self, source: str, *, announce: bool) -> None:
        defaults = build_default_task_config(source)
        self._apply_task_config(defaults)
        self._apply_db_config(defaults.db_config or default_db_config())
        if announce:
            self._log_event("info", f"已载入 {source} 的原脚本默认配置。")
            self._set_status(f"已载入 {source} 的原脚本默认配置。")

    def _apply_task_config(self, config) -> None:
        self.task_name_input.setText(config.task_name)
        self.source_combo.setCurrentText(config.source)
        self.output_dir_input.setText(config.output_dir)
        self.max_workers_input.setValue(config.max_workers)
        self.max_pages_input.setValue(config.max_pages)
        self.resume_policy_combo.setCurrentIndex(max(self.resume_policy_combo.findData(config.resume_policy), 0))
        self.show_browser_checkbox.setChecked(not config.headless)
        self.enable_ocr_checkbox.setChecked(config.enable_ocr)
        self.enable_db_checkbox.setChecked(config.enable_db)
        self._refresh_header_badges()
        self._refresh_dashboard_cards()

    def _apply_db_config(self, config: DatabaseConfig) -> None:
        self.db_host_input.setText(config.host)
        self.db_port_input.setValue(config.port)
        self.db_user_input.setText(config.user)
        self.db_password_input.setText(config.password)
        self.db_database_input.setText(config.database)
        self.db_charset_input.setText(config.charset)

    def _load_db_defaults(self) -> None:
        self._apply_db_config(default_db_config())
        self._log_event("info", "已回填 db_config.py 中的数据库默认值。")
        self._set_status("数据库配置已回填。")

    def _choose_output_dir(self) -> None:
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            self.output_dir_input.text().strip() or str(Path.cwd()),
        )
        if selected_dir:
            self.output_dir_input.setText(selected_dir)

    def _collect_payload(self) -> dict[str, object]:
        defaults = build_default_task_config(self.source_combo.currentText())
        resume_policy = str(self.resume_policy_combo.currentData())
        return {
            "task_name": self.task_name_input.text().strip() or defaults.task_name,
            "source": self.source_combo.currentText(),
            "workspace_dir": str(self.current_workspace.root) if self.current_workspace else "",
            "output_dir": self.output_dir_input.text().strip() or defaults.output_dir,
            "max_workers": self.max_workers_input.value(),
            "max_pages": self.max_pages_input.value(),
            "enable_db": self.enable_db_checkbox.isChecked(),
            "enable_ocr": self.enable_ocr_checkbox.isChecked(),
            "headless": not self.show_browser_checkbox.isChecked(),
            "auto_resume": resume_policy == "resume",
            "resume_policy": resume_policy,
            "db_host": self.db_host_input.text().strip(),
            "db_port": self.db_port_input.value(),
            "db_user": self.db_user_input.text().strip(),
            "db_password": self.db_password_input.text(),
            "db_database": self.db_database_input.text().strip(),
            "db_charset": self.db_charset_input.text().strip() or "utf8mb4",
        }

    def _build_scope_from_ui(self) -> TaskScope:
        return TaskScope(
            cities=parse_text_list(self.cities_input.toPlainText()),
            brands=self.selected_brands[:],
            series=self.selected_series[:],
            enabled_stages=list(STAGES_BY_SOURCE.get(self.source_combo.currentText(), [])),
        )

    def _create_workspace(self) -> None:
        config = build_task_config(self._collect_payload())
        scope = self._build_scope_from_ui()
        self.current_workspace = self.workspace_manager.create_workspace(config, scope)
        self.current_workspace = self.workspace_manager.load_workspace(self.current_workspace.root)
        self._hydrate_workspace(self.current_workspace, clear_log=True)
        self._log_event("info", f"工作区已准备就绪：{self.current_workspace.root}")
        self._set_status(f"工作区已准备就绪：{self.current_workspace.root}")

    def _export_workspace(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return

        default_name = str(workspace.root) + ".zip"
        file_path, _ = QFileDialog.getSaveFileName(self, "导出工作区", default_name, "Zip (*.zip)")
        if not file_path:
            return

        archive = self.workspace_manager.export_workspace(workspace.root, file_path)
        self._log_event("info", f"工作区已导出：{archive}")
        self._set_status(f"工作区已导出：{archive}")

    def _import_workspace(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "导入工作区", "", "Zip (*.zip)")
        if not file_path:
            return

        self.current_workspace = self.workspace_manager.import_workspace(file_path)
        self._hydrate_workspace(self.current_workspace, clear_log=True)
        self._log_event("info", f"工作区已导入：{self.current_workspace.root}")
        self._set_status(f"工作区已导入：{self.current_workspace.root}")

    def _export_progress(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "导出断点 JSON", "", "JSON (*.json)")
        if not file_path:
            return

        output = self.workspace_manager.export_progress_file(workspace.root, file_path)
        self._log_event("info", f"断点文件已导出：{output}")
        self._set_status(f"断点文件已导出：{output}")

    def _import_progress(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "导入断点 JSON", "", "JSON (*.json)")
        if not file_path:
            return

        progress = self.workspace_manager.import_progress_file(workspace.root, file_path)
        self.current_workspace = self.workspace_manager.load_workspace(workspace.root)
        self._refresh_workspace_summary()
        self._log_event("info", f"断点文件已导入：{file_path}")
        self._set_status(
            "断点已合并，"
            f"完成品牌 {len(progress.completed_brand_ids)}，"
            f"完成概览车系 {len(progress.completed_overview_series_ids)}，"
            f"完成详情 {len(progress.completed_detail_ids)}。"
        )

    def _merge_workspace(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "选择要合并的工作区 ZIP", "", "Zip (*.zip)")
        if not file_path:
            return

        imported = self.workspace_manager.import_workspace(
            file_path,
            target_name=f"merge-source-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        )
        merged = self.workspace_manager.merge_workspaces(
            workspace.root,
            imported.root,
            target_name=f"{Path(workspace.root).name}-merged",
        )
        self.current_workspace = merged
        self._hydrate_workspace(merged, clear_log=False)
        self._log_event("info", f"工作区已合并：{merged.root}")
        self._set_status(f"工作区已合并：{merged.root}")

    def _run_background_task(self, task_title: str, target, on_success) -> None:
        if self._task_worker is not None:
            self._warn("当前已有任务在运行，请等待当前任务结束。")
            return

        self._active_task_title = task_title
        self._set_loading_state(True, task_title, "任务已启动，等待运行反馈...")
        self._set_status(f"{task_title}进行中，请等待。")
        self._sync_db_group_state()
        self.thread_pool.setMaxThreadCount(max(1, self.max_workers_input.value()))
        worker = BackgroundTaskRunnable(target)
        worker.signals.result_ready.connect(lambda result: self._handle_task_success(task_title, result, on_success))
        worker.signals.error_raised.connect(lambda message: self._handle_task_failure(task_title, message))
        worker.signals.finished.connect(self._cleanup_finished_task)
        self._task_worker = worker
        self.thread_pool.start(worker)
        self._sync_action_state()

    def _handle_task_success(self, task_title: str, result, on_success) -> None:
        try:
            on_success(result)
        except Exception:
            self._log_event("error", traceback.format_exc().strip())
            QMessageBox.warning(self, task_title, "任务完成后刷新界面失败，请查看日志。")
        finally:
            self._set_loading_state(False, "", "等待下一步操作。")
            self._active_task_title = ""
            self._sync_db_group_state()
            self._sync_action_state()

    def _handle_task_failure(self, task_title: str, error_message: str) -> None:
        self._log_event("error", error_message.strip())
        self._set_loading_state(False, "", "等待下一步操作。")
        self._active_task_title = ""
        self._sync_db_group_state()
        self._sync_action_state()
        QMessageBox.warning(self, task_title, error_message.strip().splitlines()[-1])

    def _cleanup_finished_task(self) -> None:
        if self._task_worker is None:
            return
        self._task_worker = None
        self._sync_db_group_state()
        self._sync_action_state()

    def _set_loading_state(self, active: bool, title: str, detail: str) -> None:
        if active:
            self.loading_title_label.setText(f"当前任务：{title}")
            self.loading_detail_label.setText(detail)
            self.loading_progress.setRange(0, 0)
            self.loading_progress.show()
        else:
            self.loading_title_label.setText("当前任务：空闲")
            self.loading_detail_label.setText(detail)
            self.loading_progress.setRange(0, 1)
            self.loading_progress.setValue(0)
            self.loading_progress.hide()
        self._sync_task_dashboard()

    def _emit_runtime_event(self, level: str, message: str) -> None:
        self.runtime_event.emit(level, message)

    def _handle_runtime_event(self, level: str, message: str) -> None:
        self._log_event(level, message)
        if self._active_task_title:
            self.loading_detail_label.setText(message)
            self._sync_task_dashboard()
        self._schedule_scope_progress_refresh()

    def _test_database_connection(self) -> None:
        payload = self._collect_payload()
        payload["enable_db"] = True
        config = build_task_config(payload)
        self._run_background_task(
            "测试数据库连接",
            lambda: asyncio.run(test_db_connection(config.db_config)),
            self._after_test_database_connection,
        )

    def _load_brand_catalog(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        if workspace.config.source != "dongchedi":
            self._warn("当前只有懂车帝支持品牌目录和车系目录加载。")
            return

        self._run_background_task(
            "加载品牌目录",
            lambda: asyncio.run(self.dongchedi_runner.load_brand_catalog(workspace.root)),
            self._after_load_brand_catalog,
        )

    def _apply_brand_selection(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        if workspace.config.source != "dongchedi":
            self._warn("当前只有懂车帝支持品牌和车系选择。")
            return

        selected_ids = self._selected_item_ids(self.brand_catalog_list)
        selected = self.dongchedi_runner.select_brands(workspace.root, selected_ids)
        self.current_workspace = self.workspace_manager.load_workspace(workspace.root)
        self.selected_brands = selected
        self.selected_series = []
        self.series_catalog_list.clear()
        self._sync_brand_selection_view(preview=False)
        self._sync_series_selection_view(preview=False)
        self._refresh_workspace_summary()
        self._set_status(f"已保存品牌选择，共 {len(selected)} 个品牌。")

    def _load_series_catalog(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        if workspace.config.source != "dongchedi":
            self._warn("当前只有懂车帝支持品牌目录和车系目录加载。")
            return

        self._run_background_task(
            "加载车系目录",
            lambda: asyncio.run(self.dongchedi_runner.load_series_catalog(workspace.root)),
            self._after_load_series_catalog,
        )

    def _apply_series_selection(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        if workspace.config.source != "dongchedi":
            self._warn("当前只有懂车帝支持品牌和车系选择。")
            return

        selected_ids = self._selected_item_ids(self.series_catalog_list)
        selected = self.dongchedi_runner.select_series(workspace.root, selected_ids)
        self.current_workspace = self.workspace_manager.load_workspace(workspace.root)
        self.selected_series = selected
        self._sync_series_selection_view(preview=False)
        self._refresh_workspace_summary()
        self._set_status(f"已保存车系选择，共 {len(selected)} 个车系。")

    def _load_overviews(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        if workspace.config.source != "dongchedi":
            self._warn("当前数据源尚未接入概览抓取运行器。")
            return

        self._run_background_task(
            "抓取概览",
            lambda: asyncio.run(self.dongchedi_runner.load_overviews(workspace.root)),
            self._after_load_overviews,
        )

    def _load_details(self) -> None:
        workspace = self._require_workspace()
        if not workspace:
            return
        if workspace.config.source != "dongchedi":
            self._warn("当前数据源尚未接入详情抓取运行器。")
            return

        self._run_background_task(
            "抓取详情",
            lambda: asyncio.run(self.dongchedi_runner.load_details(workspace.root)),
            self._after_load_details,
        )

    def _after_test_database_connection(self, result: tuple[bool, str]) -> None:
        ok, message = result
        self._log_event("info" if ok else "warning", message)
        if ok:
            QMessageBox.information(self, "数据库测试", message)
        else:
            QMessageBox.warning(self, "数据库测试", message)
        self._set_status(message)

    def _after_load_brand_catalog(self, brands: list[dict]) -> None:
        if self.current_workspace is None:
            return
        self._populate_brand_catalog(brands)
        self.current_workspace = self.workspace_manager.load_workspace(self.current_workspace.root)
        self._refresh_workspace_summary()
        self._set_status(f"品牌目录加载完成，共 {len(brands)} 个品牌。")

    def _after_load_series_catalog(self, series: list[dict]) -> None:
        if self.current_workspace is None:
            return
        self._populate_series_catalog(series)
        self.current_workspace = self.workspace_manager.load_workspace(self.current_workspace.root)
        self._refresh_workspace_summary()
        self._set_status(f"车系目录加载完成，共 {len(series)} 个车系。")

    def _after_load_overviews(self, overviews: list[dict]) -> None:
        if self.current_workspace is None:
            return
        self.current_workspace = self.workspace_manager.load_workspace(self.current_workspace.root)
        self._refresh_workspace_summary()
        self._set_status(f"概览抓取完成，共 {len(overviews)} 条。")

    def _after_load_details(self, details: list[dict]) -> None:
        if self.current_workspace is None:
            return
        self.current_workspace = self.workspace_manager.load_workspace(self.current_workspace.root)
        self._refresh_workspace_summary()
        self._set_status(f"详情抓取完成，共 {len(details)} 条。")

    def _hydrate_workspace(self, workspace, *, clear_log: bool) -> None:
        self.current_workspace = workspace
        self._apply_task_config(workspace.config)
        self._apply_db_config(workspace.config.db_config or default_db_config())
        self.selected_brands = list(workspace.scope.brands)
        self.selected_series = list(workspace.scope.series)
        self.cities_input.setPlainText("\n".join(workspace.scope.cities))
        self.workspace_path_view.setText(str(workspace.root))
        if clear_log:
            self.log_view.clear()
        self._hydrate_catalog_views(workspace.root)
        self._sync_brand_selection_view(preview=False)
        self._sync_series_selection_view(preview=False)
        self._refresh_workspace_summary()
        self._sync_source_specific_sections()
        self._sync_db_group_state()
        self._sync_action_state()

    def _hydrate_catalog_views(self, workspace_root: Path) -> None:
        brand_catalog_payload = self.workspace_manager.read_result_file(workspace_root, "brand_catalog.json")
        self._populate_brand_catalog(brand_catalog_payload.get("data", []))

        series_catalog_payload = self.workspace_manager.read_result_file(workspace_root, "series_catalog.json")
        self._populate_series_catalog(series_catalog_payload.get("data", []))

    def _populate_brand_catalog(self, brands: list[dict]) -> None:
        self.brand_catalog_list.clear()
        selected_ids = {item.item_id for item in self.selected_brands}
        progress = self._safe_scope_progress()
        for item in brands:
            brand_id = str(item.get("brand_id", "")).strip()
            brand_name = str(item.get("brand_name", "")).strip()
            if not brand_id:
                continue
            base_text = f"{brand_id} | {brand_name}"
            list_item = QListWidgetItem(base_text)
            list_item.setData(
                Qt.UserRole,
                {
                    "item_id": brand_id,
                    "name": brand_name,
                    "parent_id": "",
                    "base_text": base_text,
                    "item_kind": "brand",
                },
            )
            self._apply_catalog_item_state(list_item, progress.get("brand_states", {}).get(brand_id, {}))
            self.brand_catalog_list.addItem(list_item)
            if brand_id in selected_ids:
                list_item.setSelected(True)
        self._sync_brand_selection_view(preview=False)

    def _populate_series_catalog(self, series_list: list[dict]) -> None:
        self.series_catalog_list.clear()
        selected_ids = {item.item_id for item in self.selected_series}
        progress = self._safe_scope_progress()
        for item in series_list:
            series_id = str(item.get("series_id", "")).strip()
            series_name = str(item.get("series_name", "")).strip()
            brand_id = str(item.get("brand_id", "")).strip()
            brand_name = str(item.get("brand_name", "")).strip()
            if not series_id:
                continue
            base_text = f"{series_id} | {series_name}"
            if brand_name or brand_id:
                base_text += f" | {brand_name or brand_id}"
            list_item = QListWidgetItem(base_text)
            list_item.setData(
                Qt.UserRole,
                {
                    "item_id": series_id,
                    "name": series_name,
                    "parent_id": brand_id,
                    "base_text": base_text,
                    "item_kind": "series",
                },
            )
            self._apply_catalog_item_state(list_item, progress.get("series_states", {}).get(series_id, {}))
            self.series_catalog_list.addItem(list_item)
            if series_id in selected_ids:
                list_item.setSelected(True)
        self._sync_series_selection_view(preview=False)

    def _preview_brand_selection(self) -> None:
        self._sync_brand_selection_view(preview=True)

    def _preview_series_selection(self) -> None:
        self._sync_series_selection_view(preview=True)

    def _sync_brand_selection_view(self, *, preview: bool) -> None:
        items = self._selected_catalog_items(self.brand_catalog_list) if preview else self.selected_brands
        progress = self._safe_scope_progress()
        self._populate_selection_view(
            self.brand_selection_view,
            items,
            progress.get("brand_states", {}),
            preview=preview,
            include_parent=False,
        )

    def _sync_series_selection_view(self, *, preview: bool) -> None:
        items = self._selected_catalog_items(self.series_catalog_list) if preview else self.selected_series
        progress = self._safe_scope_progress()
        self._populate_selection_view(
            self.series_selection_view,
            items,
            progress.get("series_states", {}),
            preview=preview,
            include_parent=True,
        )

    def _selected_catalog_items(self, widget: QListWidget) -> list[SelectionItem]:
        result: list[SelectionItem] = []
        for item in widget.selectedItems():
            payload = item.data(Qt.UserRole) or {}
            result.append(
                SelectionItem(
                    item_id=str(payload.get("item_id", "")),
                    name=str(payload.get("name", "")),
                    parent_id=str(payload.get("parent_id", "")),
                )
            )
        return result

    def _selected_item_ids(self, widget: QListWidget) -> list[str]:
        return [item.item_id for item in self._selected_catalog_items(widget)]

    def _select_all_in_list(self, widget: QListWidget, status_message: str) -> None:
        if widget.count() == 0:
            self._warn("当前列表为空，请先加载目录。")
            return
        widget.selectAll()
        self._set_status(status_message)

    def _clear_selection_in_list(self, widget: QListWidget, status_message: str) -> None:
        widget.clearSelection()
        self._set_status(status_message)

    def _populate_selection_view(
        self,
        widget: QListWidget,
        items: list[SelectionItem],
        state_map: dict[str, dict[str, object]],
        *,
        preview: bool,
        include_parent: bool,
    ) -> None:
        widget.clear()
        if not items:
            empty_item = QListWidgetItem("当前没有已保存项。" if not preview else "当前没有勾选项。")
            empty_item.setForeground(QBrush(QColor("#94a3b8")))
            widget.addItem(empty_item)
            return

        for item in items:
            state = state_map.get(item.item_id, {})
            base_text = f"{item.item_id} | {item.name}"
            if include_parent and item.parent_id:
                base_text += f" | {item.parent_id}"
            status_text = "未保存" if preview else self._format_scope_state_label(
                state,
                kind="series" if include_parent else "brand",
            )
            row = QListWidgetItem(f"{base_text} | {status_text}")
            color_key = "running" if preview else str(state.get("state", "pending"))
            self._apply_state_to_item(row, color_key)
            widget.addItem(row)

    def _require_workspace(self):
        if not self.current_workspace:
            self._warn("请先创建或导入工作区。")
            return None
        self.current_workspace = self.workspace_manager.load_workspace(self.current_workspace.root)
        self.workspace_path_view.setText(str(self.current_workspace.root))
        self._sync_action_state()
        return self.current_workspace

    def _refresh_workspace_summary(self) -> None:
        if not self.current_workspace:
            self.workspace_info.clear()
            self.workspace_path_view.clear()
            self._refresh_dashboard_cards()
            self._sync_action_state()
            return

        self.current_workspace = self.workspace_manager.load_workspace(self.current_workspace.root)
        summary = build_workspace_summary(self.current_workspace.root, self.workspace_manager)
        self.workspace_info.setPlainText(format_workspace_summary(summary))
        self.workspace_path_view.setText(str(self.current_workspace.root))
        self._refresh_dashboard_cards(summary)
        self._refresh_scope_progress_visuals()
        self._sync_action_state()

    def _refresh_header_badges(self) -> None:
        self.source_badge.setText(f"数据源 {self.source_combo.currentText()}")
        self.thread_badge.setText(f"并发 {self.max_workers_input.value()}")
        resume_label = "继续断点" if str(self.resume_policy_combo.currentData()) == "resume" else "清空重跑"
        self.resume_badge.setText(resume_label)
        browser_label = "显示浏览器" if self.show_browser_checkbox.isChecked() else "无头运行"
        self.browser_badge.setText(browser_label)

    def _refresh_dashboard_cards(self, summary: dict[str, Any] | None = None) -> None:
        if summary is None and self.current_workspace:
            try:
                summary = build_workspace_summary(self.current_workspace.root, self.workspace_manager)
            except Exception:
                summary = None

        if summary is None:
            self.workspace_metric_value.setText("未创建")
            self.workspace_metric_note.setText("先创建或导入工作区，再开始目录和抓取流程")
            self.scope_metric_value.setText("品牌 0 | 车系 0")
            self.scope_metric_note.setText("支持品牌、车系、城市和断点文件一起迁移")
            self.result_metric_value.setText("概览 0 | 详情 0")
            self.result_metric_note.setText("目录和结果会在本地持续落盘")
            self._sync_task_dashboard()
            return

        workspace_name = Path(summary["workspace_root"]).name or str(summary["workspace_root"])
        self.workspace_metric_value.setText(workspace_name)
        self.workspace_metric_note.setText(str(summary["workspace_root"]))
        self.scope_metric_value.setText(
            f"品牌 {summary['selected_brand_total']} | 车系 {summary['selected_series_total']}"
        )
        self.scope_metric_note.setText(
            f"目录完成 {summary['completed_brand_total']} | 概览完成 {summary['completed_overview_series_total']}"
        )
        counts = summary["counts"]
        self.result_metric_value.setText(f"概览 {counts['overviews.json']} | 详情 {counts['details.json']}")
        self.result_metric_note.setText(
            f"品牌目录 {counts['brand_catalog.json']} | 车系目录 {counts['series_catalog.json']}"
        )
        self._sync_task_dashboard()

    def _sync_task_dashboard(self) -> None:
        active_title = self._active_task_title or "空闲"
        detail = self.loading_detail_label.text().strip() or "等待下一步操作。"
        if not self._active_task_title and self.status_label.text().strip():
            detail = self.status_label.text().strip()
        self.task_metric_value.setText(active_title)
        self.task_metric_note.setText(detail)

    def _safe_scope_progress(self) -> dict[str, Any]:
        if not self.current_workspace:
            return {"brand_states": {}, "series_states": {}}
        try:
            return build_scope_progress(self.current_workspace.root, self.workspace_manager)
        except Exception:
            return {"brand_states": {}, "series_states": {}}

    def _schedule_scope_progress_refresh(self) -> None:
        if not self.current_workspace:
            return
        if not self._scope_refresh_timer.isActive():
            self._scope_refresh_timer.start()

    def _refresh_scope_progress_visuals(self) -> None:
        if not self.current_workspace:
            return
        progress = self._safe_scope_progress()
        self._apply_list_state_map(self.brand_catalog_list, progress.get("brand_states", {}))
        self._apply_list_state_map(self.series_catalog_list, progress.get("series_states", {}))
        self._sync_brand_selection_view(preview=False)
        self._sync_series_selection_view(preview=False)

    def _apply_list_state_map(self, widget: QListWidget, state_map: dict[str, dict[str, object]]) -> None:
        for index in range(widget.count()):
            item = widget.item(index)
            payload = item.data(Qt.UserRole) or {}
            item_id = str(payload.get("item_id", ""))
            self._apply_catalog_item_state(item, state_map.get(item_id, {}))

    def _apply_catalog_item_state(self, item: QListWidgetItem, state_info: dict[str, object]) -> None:
        payload = item.data(Qt.UserRole) or {}
        base_text = str(payload.get("base_text", item.text()))
        kind = str(payload.get("item_kind", "series"))
        status_text = self._format_scope_state_label(state_info, kind=kind)
        item.setText(f"{base_text} | {status_text}")
        item.setToolTip(status_text)
        self._apply_state_to_item(item, str(state_info.get("state", "pending")))

    def _format_scope_state_label(self, state_info: dict[str, object], *, kind: str) -> str:
        state = str(state_info.get("state", "pending"))
        if kind == "brand":
            selected_total = int(state_info.get("selected_series_total", 0) or 0)
            completed_total = int(state_info.get("completed_series_total", 0) or 0)
            if state == "detail_done":
                return f"详情已完成 | 车系 {completed_total}/{selected_total}" if selected_total else "详情已完成"
            if state == "series_loaded":
                return f"车系目录已完成 | 详情 {completed_total}/{selected_total}" if selected_total else "车系目录已完成"
            return "待执行"

        overview_total = int(state_info.get("overview_total", 0) or 0)
        detail_done_total = int(state_info.get("detail_done_total", 0) or 0)
        if state == "detail_done":
            return (
                f"详情已完成 | 车辆 {detail_done_total}/{overview_total}"
                if overview_total
                else "详情已完成"
            )
        if state == "overview_done":
            return (
                f"概览已完成 | 详情 {detail_done_total}/{overview_total}"
                if overview_total
                else "概览已完成"
            )
        return "待执行"

    def _apply_state_to_item(self, item: QListWidgetItem, state: str) -> None:
        color = STATE_COLORS.get(state, STATE_COLORS["pending"])
        background = STATE_BACKGROUNDS.get(state, STATE_BACKGROUNDS["pending"])
        font = item.font()
        font.setBold(state != "pending")
        item.setFont(font)
        item.setForeground(QBrush(color))
        item.setBackground(QBrush(background))

    def _sync_source_specific_sections(self) -> None:
        is_dongchedi = self.source_combo.currentText() == "dongchedi"
        self.dongchedi_scope_group.setVisible(is_dongchedi)
        self.city_group.setVisible(not is_dongchedi)
        if is_dongchedi:
            self.scope_hint_label.setText("懂车帝先加载品牌目录，再保存品牌选择，最后按所选品牌加载车系并抓取。")
        else:
            self.scope_hint_label.setText("瓜子当前保留基础配置与城市范围，桌面运行器暂未接入。")

    def _sync_db_group_state(self) -> None:
        is_busy = self._task_worker is not None
        self.database_group.setEnabled(self.enable_db_checkbox.isChecked() and not is_busy)

    def _sync_action_state(self) -> None:
        is_busy = self._task_worker is not None
        has_workspace = self.current_workspace is not None and not is_busy
        is_dongchedi = self.source_combo.currentText() == "dongchedi"
        self.load_defaults_button.setEnabled(not is_busy)
        self.create_workspace_button.setEnabled(not is_busy)
        self.import_workspace_button.setEnabled(not is_busy)
        self.test_db_button.setEnabled(not is_busy)
        self.load_db_defaults_button.setEnabled(not is_busy)
        self.source_combo.setEnabled(not is_busy)
        self.task_name_input.setEnabled(not is_busy)
        self.output_dir_input.setEnabled(not is_busy)
        self.output_dir_button.setEnabled(not is_busy)
        self.max_workers_input.setEnabled(not is_busy)
        self.max_pages_input.setEnabled(not is_busy)
        self.resume_policy_combo.setEnabled(not is_busy)
        self.show_browser_checkbox.setEnabled(not is_busy)
        self.enable_ocr_checkbox.setEnabled(not is_busy)
        self.enable_db_checkbox.setEnabled(not is_busy)
        self.db_host_input.setEnabled(not is_busy and self.enable_db_checkbox.isChecked())
        self.db_port_input.setEnabled(not is_busy and self.enable_db_checkbox.isChecked())
        self.db_user_input.setEnabled(not is_busy and self.enable_db_checkbox.isChecked())
        self.db_password_input.setEnabled(not is_busy and self.enable_db_checkbox.isChecked())
        self.db_database_input.setEnabled(not is_busy and self.enable_db_checkbox.isChecked())
        self.db_charset_input.setEnabled(not is_busy and self.enable_db_checkbox.isChecked())
        self.cities_input.setEnabled(not is_busy)
        self.brand_catalog_list.setEnabled(not is_busy)
        self.series_catalog_list.setEnabled(not is_busy)

        for button in (
            self.export_workspace_button,
            self.import_progress_button,
            self.export_progress_button,
            self.merge_workspace_button,
            self.refresh_button,
        ):
            button.setEnabled(has_workspace)

        for button in (
            self.load_brand_catalog_button,
            self.apply_brand_selection_button,
            self.select_all_brands_button,
            self.clear_brand_selection_button,
            self.load_series_catalog_button,
            self.apply_series_selection_button,
            self.select_all_series_button,
            self.clear_series_selection_button,
            self.load_overviews_button,
            self.load_details_button,
        ):
            button.setEnabled(has_workspace and is_dongchedi)

    def _log_event(self, level: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{timestamp}] [{level.upper()}] {message}")

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
        self._sync_task_dashboard()

    def _warn(self, message: str) -> None:
        QMessageBox.warning(self, "提示", message)
