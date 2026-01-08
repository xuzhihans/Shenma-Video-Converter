import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QPushButton, QListWidget, QTableWidget, QTableWidgetItem, 
                               QAbstractItemView, QHeaderView, QFileDialog, QGroupBox, QRadioButton, 
                               QCheckBox, QButtonGroup, QSlider, QLineEdit, QProgressBar, QMessageBox,
                               QFrame, QScrollArea, QGridLayout, QStyle, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, QMimeData, QSize, Signal, Slot, QEvent, QPoint
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QAction, QMouseEvent

class FormatCellWidget(QWidget):
    formatChanged = Signal()

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(10)
        
        self.chk_mp4 = QCheckBox("MP4")
        self.chk_mkv = QCheckBox("MKV")
        self.chk_mp4.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.chk_mkv.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout.addWidget(self.chk_mp4)
        layout.addWidget(self.chk_mkv)
        
        self.chk_mp4.stateChanged.connect(self.formatChanged)
        self.chk_mkv.stateChanged.connect(self.formatChanged)

    def set_data(self, mp4_checked, mkv_checked):
        self.chk_mp4.blockSignals(True)
        self.chk_mkv.blockSignals(True)
        self.chk_mp4.setChecked(mp4_checked)
        self.chk_mkv.setChecked(mkv_checked)
        self.chk_mp4.blockSignals(False)
        self.chk_mkv.blockSignals(False)

class TrimCellWidget(QWidget):
    trimChanged = Signal()

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        
        self.edit_start = QLineEdit("0")
        self.edit_start.setPlaceholderText("Start")
        self.edit_start.setFixedWidth(50)
        
        self.edit_end = QLineEdit("0")
        self.edit_end.setPlaceholderText("End")
        self.edit_end.setFixedWidth(50)
        
        layout.addWidget(QLabel("开始第n(秒):"))
        layout.addWidget(self.edit_start)
        layout.addWidget(QLabel("倒数第n(秒):"))
        layout.addWidget(self.edit_end)
        
        self.edit_start.editingFinished.connect(self.trimChanged)
        self.edit_end.editingFinished.connect(self.trimChanged)

    def set_data(self, start, end):
        self.edit_start.blockSignals(True)
        self.edit_end.blockSignals(True)
        self.edit_start.setText(str(start))
        self.edit_end.setText(str(end))
        self.edit_start.blockSignals(False)
        self.edit_end.blockSignals(False)

class StabilizeCellWidget(QWidget):
    stabilizeChanged = Signal()

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 35)
        self.slider.setFixedWidth(80)
        
        self.label = QLabel("0")
        self.label.setFixedWidth(25)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.slider)
        layout.addWidget(self.label)
        
        self.slider.valueChanged.connect(lambda v: self.label.setText(str(v)))
        self.slider.sliderReleased.connect(self.stabilizeChanged) # Only update on release to avoid spam

    def set_data(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(int(value))
        self.label.setText(str(value))
        self.slider.blockSignals(False)

class QualityCellWidget(QWidget):
    qualityChanged = Signal()

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        
        self.chk_lossless = QCheckBox("无损")
        self.chk_hd = QCheckBox("高清")
        self.chk_balanced = QCheckBox("平衡")
        self.chk_compact = QCheckBox("小体积")
        
        for chk in [self.chk_lossless, self.chk_hd, self.chk_balanced, self.chk_compact]:
            chk.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout.addWidget(self.chk_lossless)
        layout.addWidget(self.chk_hd)
        layout.addWidget(self.chk_balanced)
        layout.addWidget(self.chk_compact)
        
        self.chk_lossless.stateChanged.connect(self.qualityChanged)
        self.chk_hd.stateChanged.connect(self.qualityChanged)
        self.chk_balanced.stateChanged.connect(self.qualityChanged)
        self.chk_compact.stateChanged.connect(self.qualityChanged)

    def set_data(self, qualities):
        self.blockSignals(True) # Block self signal? No, individual widgets.
        # Actually easier to block signals of children
        for chk in [self.chk_lossless, self.chk_hd, self.chk_balanced, self.chk_compact]:
            chk.blockSignals(True)
            
        self.chk_lossless.setChecked("lossless" in qualities)
        self.chk_hd.setChecked("hd" in qualities)
        self.chk_balanced.setChecked("balanced" in qualities)
        self.chk_compact.setChecked("compact" in qualities)
        
        for chk in [self.chk_lossless, self.chk_hd, self.chk_balanced, self.chk_compact]:
            chk.blockSignals(False)

class RotationCellWidget(QWidget):
    rotationChanged = Signal()

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        
        self.group = QButtonGroup(self)
        
        self.radio_none = QRadioButton("Φ 保持")
        self.radio_left = QRadioButton("↶ 90°")
        self.radio_right = QRadioButton("↷ 90°")
        self.radio_180 = QRadioButton("⥯ 180°")
        
        self.group.addButton(self.radio_none, 0)
        self.group.addButton(self.radio_left, 1)
        self.group.addButton(self.radio_right, 2)
        self.group.addButton(self.radio_180, 3)
        
        for r in [self.radio_none, self.radio_left, self.radio_right, self.radio_180]:
            r.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        layout.addWidget(self.radio_none)
        layout.addWidget(self.radio_left)
        layout.addWidget(self.radio_right)
        layout.addWidget(self.radio_180)
        
        # Connect group signal
        self.group.idClicked.connect(self.rotationChanged)

    def set_data(self, rotation_id):
        self.group.blockSignals(True)
        btn = self.group.button(rotation_id)
        if btn:
            btn.setChecked(True)
        else:
            self.radio_none.setChecked(True)
        self.group.blockSignals(False)

class FileTableWidget(QTableWidget):
    fileDropped = Signal(list)
    requestAddFile = Signal()
    rightDoubleClicked = Signal(int, int)
    quickOpenRequested = Signal(int) # row

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        # Columns: No, Filename, Path, Size, Status, Format, Quality, Rotation, Trim, Stabilize
        self.headers = ["序号", "文件名", "路径", "大小", "状态", "格式", "质量", "旋转", "剪切", "增稳"]
        self.setColumnCount(len(self.headers))
        self.setHorizontalHeaderLabels(self.headers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.verticalHeader().setVisible(False) # Hide default row numbers
        self.setContextMenuPolicy(Qt.CustomContextMenu) # Enable Custom Context Menu
    
    def mousePressEvent(self, event):
        # Check for Alt + Left Click
        if event.button() == Qt.MouseButton.LeftButton:
            modifiers = event.modifiers()
            if modifiers & Qt.KeyboardModifier.AltModifier:
                item = self.itemAt(event.position().toPoint())
                if item:
                    self.quickOpenRequested.emit(item.row())
                    return # Consume event to prevent selection change if desired, or call super to select
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(event.position().toPoint())
            if item:
                self.rightDoubleClicked.emit(item.row(), item.column())
            return

        if not self.indexAt(event.pos()).isValid():
            self.requestAddFile.emit()
        super().mouseDoubleClickEvent(event)

    def applyResizeModeEmpty(self):
        header = self.horizontalHeader()
        for col in range(self.columnCount()):
            if col == 2:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            else:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
    
    def applyResizeModeWithContent(self):
        header = self.horizontalHeader()
        for col in range(self.columnCount()):
            if col == 2:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            else:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        file_paths = []
        valid_exts = {'.mp4', '.mkv', '.avi', '.mov', '.flv'}
        
        for url in urls:
            path = url.toLocalFile()
            if os.path.isfile(path):
                if os.path.splitext(path)[1].lower() in valid_exts:
                    file_paths.append(path)
            elif os.path.isdir(path):
                # Only first level
                try:
                    for entry in os.listdir(path):
                        full_path = os.path.join(path, entry)
                        if os.path.isfile(full_path):
                            if os.path.splitext(full_path)[1].lower() in valid_exts:
                                file_paths.append(full_path)
                except Exception as e:
                    print(f"Error reading dir: {e}")
        
        if file_paths:
            self.fileDropped.emit(file_paths)

class TaskTableWidget(QTableWidget):
    rightDoubleClicked = Signal(int, int) # row, col
    quickOpenRequested = Signal(int) # row

    def mousePressEvent(self, event):
        # Check for Alt + Left Click
        if event.button() == Qt.MouseButton.LeftButton:
            modifiers = event.modifiers()
            if modifiers & Qt.KeyboardModifier.AltModifier:
                item = self.itemAt(event.position().toPoint())
                if item:
                    self.quickOpenRequested.emit(item.row())
                    return 
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(event.position().toPoint())
            if item:
                self.rightDoubleClicked.emit(item.row(), item.column())
        else:
            super().mouseDoubleClickEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("神马视频转换")
        self.resize(1000, 700) # Slightly larger than 800x600 for better view

        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # 1. File Management & Transcode Settings Zone
        self.init_file_zone()
        
        # 2. Global Config Zone
        self.init_global_config_zone()
        
        # 3. Task Progress Zone
        self.init_task_zone()
        
        # 4. Action Button Zone
        self.init_action_zone()

    def init_file_zone(self):
        # Group Box
        self.file_group = QGroupBox("1. 文件管理及转码设置")
        layout = QVBoxLayout(self.file_group)

        # Buttons Row
        btn_layout = QHBoxLayout()
        self.btn_add_file = QPushButton("添加文件")
        self.btn_del_sel = QPushButton("删除选中")
        self.btn_clear_all = QPushButton("清空列表")
        
        btn_layout.addWidget(self.btn_add_file)
        btn_layout.addWidget(self.btn_del_sel)
        btn_layout.addWidget(self.btn_clear_all)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)

        # File List Table
        self.file_table = FileTableWidget()
        layout.addWidget(self.file_table)
        
        # Add to main layout (stretch factor 2)
        self.main_layout.addWidget(self.file_group, 2)

    def init_global_config_zone(self):
        self.global_group = QGroupBox("2. 全局配置 (默认配置 / 批量修改)")
        layout = QVBoxLayout(self.global_group) # Changed to VBox to stack settings and path

        # --- Transcode Settings (Moved from File Zone) ---
        settings_frame = QFrame()
        settings_layout = QHBoxLayout(settings_frame)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        
        # (1) Output Format
        format_group = QGroupBox("输出格式")
        format_layout = QVBoxLayout()
        self.chk_mp4 = QCheckBox("MP4")
        self.chk_mkv = QCheckBox("MKV")
        self.chk_mp4.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.chk_mkv.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.chk_mp4.setChecked(True) # Default
        format_layout.addWidget(self.chk_mp4)
        format_layout.addWidget(self.chk_mkv)
        format_group.setLayout(format_layout)
        settings_layout.addWidget(format_group)

        # (2) Compression Quality
        quality_group = QGroupBox("压缩质量")
        quality_layout = QVBoxLayout()
        self.chk_lossless = QCheckBox("无损 (Lossless)")
        self.chk_hd = QCheckBox("高清 (HD)")
        self.chk_balanced = QCheckBox("平衡 (Balanced)")
        self.chk_compact = QCheckBox("小体积 (Compact)")
        
        for chk in [self.chk_lossless, self.chk_hd, self.chk_balanced, self.chk_compact]:
            chk.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.chk_balanced.setChecked(True) # Default
        quality_layout.addWidget(self.chk_lossless)
        quality_layout.addWidget(self.chk_hd)
        quality_layout.addWidget(self.chk_balanced)
        quality_layout.addWidget(self.chk_compact)
        quality_group.setLayout(quality_layout)
        settings_layout.addWidget(quality_group)

        # (3) Rotation
        rotate_group = QGroupBox("视频旋转")
        rotate_layout = QVBoxLayout()
        self.radio_rot_none = QRadioButton("保持 Φ 0°")
        self.radio_rot_left = QRadioButton("左旋 ↶ 90°")
        self.radio_rot_right = QRadioButton("右旋 ↷ 90°")
        self.radio_rot_180 = QRadioButton("翻转 ⥯ 180°")
        self.radio_rot_none.setChecked(True)
        
        self.rot_group_btn = QButtonGroup()
        self.rot_group_btn.addButton(self.radio_rot_none, 0)
        self.rot_group_btn.addButton(self.radio_rot_left, 1)
        self.rot_group_btn.addButton(self.radio_rot_right, 2)
        self.rot_group_btn.addButton(self.radio_rot_180, 3)
        
        rotate_layout.addWidget(self.radio_rot_none)
        rotate_layout.addWidget(self.radio_rot_left)
        rotate_layout.addWidget(self.radio_rot_right)
        rotate_layout.addWidget(self.radio_rot_180)
        rotate_group.setLayout(rotate_layout)
        settings_layout.addWidget(rotate_group)

        # (4) Trim
        trim_group = QGroupBox("剪切 (秒)")
        trim_layout = QGridLayout()
        trim_layout.addWidget(QLabel("开始第n(秒):"), 0, 0)
        self.edit_trim_start = QLineEdit("0")
        trim_layout.addWidget(self.edit_trim_start, 0, 1)
        trim_layout.addWidget(QLabel("倒数第n(秒):"), 1, 0)
        self.edit_trim_end = QLineEdit("0")
        trim_layout.addWidget(self.edit_trim_end, 1, 1)
        trim_group.setLayout(trim_layout)
        settings_layout.addWidget(trim_group)

        # (5) Stabilization
        stab_group = QGroupBox("增稳处理(0-35)")
        stab_layout = QVBoxLayout()
        stab_layout.setSpacing(2)  # Reduce spacing between elements
        
        stab_info = QLabel("0为不增稳，1-35为增稳等级(建议<30)\n开启会极大增加耗时")
        stab_info.setStyleSheet("color: gray; font-size: 11px;")
        stab_info.setWordWrap(True)
        stab_layout.addWidget(stab_info)

        self.stab_slider = QSlider(Qt.Orientation.Horizontal)
        self.stab_slider.setRange(0, 35)
        self.stab_slider.setValue(0)
        
        stab_val_layout = QHBoxLayout()
        self.stab_edit = QLineEdit("0")
        self.stab_edit.setFixedWidth(40)
        stab_val_layout.addWidget(self.stab_slider)
        stab_val_layout.addWidget(self.stab_edit)
        
        stab_layout.addLayout(stab_val_layout)
        stab_group.setLayout(stab_layout)
        settings_layout.addWidget(stab_group)
        
        layout.addWidget(settings_frame)

        # --- Global Config (Path & Threads) ---
        global_bottom_layout = QHBoxLayout()

        # Output Dir
        dir_layout = QVBoxLayout()
        dir_radio_layout = QHBoxLayout()
        self.radio_out_same = QRadioButton("同文件夹目录")
        self.radio_out_custom = QRadioButton("用户自定义目录")
        self.radio_out_same.setChecked(True)
        self.out_group_btn = QButtonGroup()
        self.out_group_btn.addButton(self.radio_out_same)
        self.out_group_btn.addButton(self.radio_out_custom)
        
        dir_radio_layout.addWidget(self.radio_out_same)
        dir_radio_layout.addWidget(self.radio_out_custom)
        
        self.out_path_display = QLineEdit()
        self.out_path_display.setReadOnly(True)
        self.out_path_display.setPlaceholderText("请选择输出目录...")
        self.out_path_display.setEnabled(False)
        
        self.btn_browse_out = QPushButton("浏览")
        self.btn_browse_out.setEnabled(False)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.out_path_display)
        path_layout.addWidget(self.btn_browse_out)

        dir_layout.addLayout(dir_radio_layout)
        dir_layout.addLayout(path_layout)
        
        global_bottom_layout.addLayout(dir_layout, 2)

        # Thread Count
        thread_layout = QVBoxLayout()
        thread_layout.addWidget(QLabel("同时任务数 (1-15):"))
        
        thread_ctrl_layout = QHBoxLayout()
        self.thread_slider = QSlider(Qt.Orientation.Horizontal)
        self.thread_slider.setRange(1, 15)
        self.thread_slider.setValue(3) # Default
        self.thread_edit = QLineEdit("3")
        self.thread_edit.setFixedWidth(40)
        
        thread_ctrl_layout.addWidget(self.thread_slider)
        thread_ctrl_layout.addWidget(self.thread_edit)
        thread_layout.addLayout(thread_ctrl_layout)
        
        global_bottom_layout.addLayout(thread_layout, 1)
        
        layout.addLayout(global_bottom_layout)

        self.main_layout.addWidget(self.global_group, 0)

    def init_task_zone(self):
        self.task_group = QGroupBox("3. 任务进度")
        layout = QVBoxLayout(self.task_group)
        
        # Tool bar for task list
        tool_layout = QHBoxLayout()
        tool_layout.addStretch()
        
        self.btn_scroll_follow = QPushButton("↓↓")
        self.btn_scroll_follow.setToolTip("自动跟随最新任务")
        self.btn_scroll_follow.setCheckable(True)
        self.btn_scroll_follow.setChecked(True)
        self.btn_scroll_follow.setFixedSize(40, 24)
        
        tool_layout.addWidget(self.btn_scroll_follow)
        layout.addLayout(tool_layout)
        
        self.task_table = TaskTableWidget()
        self.task_table.setColumnCount(6)
        self.task_table.setHorizontalHeaderLabels(["序号", "文件名", "原路径", "输出路径", "进度", "状态"])
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.task_table)
        self.main_layout.addWidget(self.task_group, 2)
        
        # Scroll Logic
        self.task_table.verticalScrollBar().valueChanged.connect(self.check_task_scroll)
        self.btn_scroll_follow.clicked.connect(self.toggle_task_follow)

        # Interaction Policy
        self.task_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.task_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.task_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def check_task_scroll(self, value):
        v_scroll = self.task_table.verticalScrollBar()
        if value < v_scroll.maximum():
            # User scrolled up
            if self.btn_scroll_follow.isChecked():
                self.btn_scroll_follow.blockSignals(True)
                self.btn_scroll_follow.setChecked(False)
                self.btn_scroll_follow.setText("↓")
                self.btn_scroll_follow.blockSignals(False)
        elif value == v_scroll.maximum():
            # User at bottom
            if not self.btn_scroll_follow.isChecked():
                self.btn_scroll_follow.blockSignals(True)
                self.btn_scroll_follow.setChecked(True)
                self.btn_scroll_follow.setText("↓↓")
                self.btn_scroll_follow.blockSignals(False)

    def toggle_task_follow(self):
        if self.btn_scroll_follow.isChecked():
            # User clicked to Enable Follow -> Scroll to bottom
            self.btn_scroll_follow.setText("↓↓")
            self.task_table.scrollToBottom()
        else:
            # User clicked to Disable? (Usually clicking button is to Enable)
            # If it was Checked and they clicked, it becomes Unchecked.
            # But the button is a toggle.
            # If they uncheck it manually, it just pauses.
            self.btn_scroll_follow.setText("↓")

    def init_action_zone(self):
        # Action Buttons
        layout = QHBoxLayout()
        self.btn_help = QPushButton("使用说明")
        self.btn_cancel_all = QPushButton("取消所有任务")
        self.btn_clear_tasks = QPushButton("清空任务列表") # New
        self.task_table.verticalHeader().setVisible(False)
        self.btn_cancel_all.setEnabled(False)
        
        self.btn_pause = QPushButton("暂停任务") # New
        self.btn_pause.setEnabled(False)
        self.btn_pause.setVisible(False) # Initially hidden

        self.btn_start = QPushButton("开始转换")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        layout.addStretch()
        layout.addWidget(self.btn_help)
        layout.addWidget(self.btn_clear_tasks)
        layout.addWidget(self.btn_cancel_all)
        layout.addWidget(self.btn_pause)
        layout.addWidget(self.btn_start)
        
        self.main_layout.addLayout(layout, 0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
