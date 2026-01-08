import sys
import os
import uuid
import subprocess
from PySide6.QtWidgets import (QApplication, QTableWidgetItem, QHeaderView, QMessageBox, 
                               QFileDialog, QMenu, QDialog, QVBoxLayout, QHBoxLayout, 
                               QLabel, QStyle, QDialogButtonBox)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Slot, QPoint
from gui import MainWindow, FormatCellWidget, QualityCellWidget, RotationCellWidget, TrimCellWidget, StabilizeCellWidget
from worker import Scheduler, TranscodeTask, WorkerSignals, TaskStatus
from utils import get_ffmpeg_path, get_base_path

class ShenmaConverter(MainWindow):
    def __init__(self):
        super().__init__()
        
        # Data
        self.file_list = [] # List of dicts: {path, size, name, status, config}
        self.tasks = {} # task_id -> task_obj
        
        # Scheduler
        self.scheduler = Scheduler()
        
        # Connect UI Signals
        self.connect_signals()
        
        # Initial header mode for empty table
        self.file_table.applyResizeModeEmpty()
        
        # Check FFmpeg
        self.check_ffmpeg()

        # Set Window Icon
        icon_path = os.path.join(get_base_path(), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def connect_signals(self):
        # File Zone
        self.btn_add_file.clicked.connect(self.add_files_dialog)
        self.btn_del_sel.clicked.connect(self.delete_selected_files)
        self.btn_clear_all.clicked.connect(self.clear_all_files)
        self.file_table.fileDropped.connect(self.add_files)
        self.file_table.requestAddFile.connect(self.add_files_dialog)
        self.file_table.cellDoubleClicked.connect(self.on_file_double_click)
        self.file_table.rightDoubleClicked.connect(self.on_file_right_double_click)
        self.file_table.quickOpenRequested.connect(self.open_file_folder)
        self.file_table.customContextMenuRequested.connect(self.show_file_context_menu)
        self.stab_slider.valueChanged.connect(lambda v: self.stab_edit.setText(str(v)))
        self.stab_edit.textChanged.connect(lambda t: self.stab_slider.setValue(int(t) if t.isdigit() else 0))

        # Global Config
        self.btn_browse_out.clicked.connect(self.browse_output_dir)
        self.radio_out_custom.toggled.connect(self.toggle_output_browse)
        
        # Global Sync Signals
        self.chk_mp4.stateChanged.connect(self.sync_global_formats)
        self.chk_mkv.stateChanged.connect(self.sync_global_formats)
        
        self.chk_lossless.stateChanged.connect(self.sync_global_qualities)
        self.chk_hd.stateChanged.connect(self.sync_global_qualities)
        self.chk_balanced.stateChanged.connect(self.sync_global_qualities)
        self.chk_compact.stateChanged.connect(self.sync_global_qualities)
        
        self.rot_group_btn.idClicked.connect(self.sync_global_rotation)
        
        self.edit_trim_start.textChanged.connect(self.sync_global_trim)
        self.edit_trim_end.textChanged.connect(self.sync_global_trim)
        
        self.stab_slider.valueChanged.connect(self.sync_global_stabilization)
        
        # Thread slider sync
        self.thread_slider.valueChanged.connect(lambda v: self.thread_edit.setText(str(v)))
        self.thread_edit.textChanged.connect(lambda t: self.thread_slider.setValue(int(t) if t.isdigit() else 1))
        self.thread_slider.valueChanged.connect(self.update_scheduler_threads)

        # Action Zone
        self.btn_start.clicked.connect(self.start_conversion)
        self.btn_cancel_all.clicked.connect(self.cancel_all_tasks)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_clear_tasks.clicked.connect(self.clear_task_list)
        self.btn_help.clicked.connect(self.show_help_dialog)
        
        self.task_table.cellDoubleClicked.connect(self.on_task_double_click)
        self.task_table.rightDoubleClicked.connect(self.on_task_right_double_click)
        self.task_table.quickOpenRequested.connect(self.open_task_folder)
        self.task_table.customContextMenuRequested.connect(self.show_task_context_menu)

    def show_help_dialog(self):
        title = "使用说明"
        content = """
        <h3>神马视频处理</h3>
        <p><b>发行版本号：</b>2026.1.8-1.0.0</p>
        <p>高效批量视频工具，支持MP4/MKV转码、智能增稳、剪切旋转。多线程并行加速，操作简洁，一键轻松处理。</p>
        <hr>
        <h4>软件快捷使用说明：</h4>
        <ol>
            <li><b>快速导入</b>：在文件列表空白区域双击，即可选取并导入视频文件。</li>
            <li><b>预览播放</b>：鼠标左键双击文件列表项，即可调用系统默认播放器进行预览。</li>
            <li><b>定位目录</b>：右键单击或按住 Alt 键 + 左键单击列表项，快速打开文件或任务所在的文件夹。</li>
            <li><b>批量转码</b>：配置全局选项后可自动应用，支持批量输出多种格式与质量的视频。</li>
        </ol>
        <hr>
        <p>github: <a href='https://github.com/xuzhihans'>https://github.com/xuzhihans</a></p>
        <p>微信号：xzxz721</p>
        """
        QMessageBox.about(self, title, content)

    def check_ffmpeg(self):
        # Check if ffmpeg is in path or current dir
        # We can try running 'ffmpeg -version'
        try:
            import subprocess
            subprocess.run([get_ffmpeg_path(), "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except FileNotFoundError:
            QMessageBox.warning(self, "缺少组件", "未找到 FFmpeg 可执行文件。\n请确保 ffmpeg.exe 位于程序目录下。")

    # --- File Management ---

    def add_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择视频文件", "", "Video Files (*.mp4 *.mkv *.avi *.mov *.flv)")
        if files:
            self.add_files(files)

    def add_files(self, paths):
        existing_paths = {f['path'] for f in self.file_list}
        added_count = 0
        default_config = self.get_current_global_config()
        
        for path in paths:
            if path in existing_paths:
                continue
            
            if not os.path.exists(path):
                continue

            size_mb = os.path.getsize(path) / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB"
            if size_mb > 1024:
                size_str = f"{size_mb/1024:.2f} GB"

            file_data = {
                "path": path,
                "name": os.path.basename(path),
                "size": size_str,
                "status": "待转码",
                "config": default_config.copy()
            }
            self.file_list.append(file_data)
            added_count += 1
            
            # Add to Table
            row = self.file_table.rowCount()
            self.file_table.insertRow(row)
            self.update_table_row(row, file_data)
        
        if added_count == 0 and paths:
            # Maybe hint duplicates?
            pass
        
        if self.file_table.rowCount() > 0:
            self.file_table.applyResizeModeWithContent()

    def update_table_row(self, row, data):
        def create_readonly_item(text):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            return item

        self.file_table.setItem(row, 0, create_readonly_item(str(row + 1)))
        self.file_table.setItem(row, 1, create_readonly_item(data['name']))
        self.file_table.setItem(row, 2, create_readonly_item(data['path'])) # Tooltip auto
        self.file_table.setItem(row, 3, create_readonly_item(data['size']))
        self.file_table.setItem(row, 4, create_readonly_item(data['status']))
        
        # Format Widget
        widget = self.file_table.cellWidget(row, 5)
        if not widget:
            widget = FormatCellWidget()
            widget.formatChanged.connect(lambda w=widget: self.on_table_format_changed(w))
            self.file_table.setCellWidget(row, 5, widget)
        
        is_mp4 = "mp4" in data['config']['formats']
        is_mkv = "mkv" in data['config']['formats']
        widget.set_data(is_mp4, is_mkv)
        
        # Quality Widget (Col 6)
        widget_q = self.file_table.cellWidget(row, 6)
        if not widget_q:
            widget_q = QualityCellWidget()
            widget_q.qualityChanged.connect(lambda w=widget_q: self.on_table_quality_changed(w))
            self.file_table.setCellWidget(row, 6, widget_q)
        widget_q.set_data(data['config']['qualities'])

        # Rotation Widget (Col 7)
        widget_r = self.file_table.cellWidget(row, 7)
        if not widget_r:
            widget_r = RotationCellWidget()
            widget_r.rotationChanged.connect(lambda w=widget_r: self.on_table_rotation_changed(w))
            self.file_table.setCellWidget(row, 7, widget_r)
        widget_r.set_data(data['config']['rotation'])
        
        widget_t = self.file_table.cellWidget(row, 8)
        if not widget_t:
            widget_t = TrimCellWidget()
            widget_t.trimChanged.connect(lambda w=widget_t: self.on_table_trim_changed(w))
            self.file_table.setCellWidget(row, 8, widget_t)
        widget_t.set_data(data['config']['trim_start'], data['config']['trim_end'])
        
        widget_s = self.file_table.cellWidget(row, 9)
        if not widget_s:
            widget_s = StabilizeCellWidget()
            widget_s.stabilizeChanged.connect(lambda w=widget_s: self.on_table_stabilize_changed(w))
            self.file_table.setCellWidget(row, 9, widget_s)
        widget_s.set_data(data['config']['stabilization'])
    
    def on_file_double_click(self, row, col):
        if row < 0 or row >= len(self.file_list): return
        # Don't play if clicking on editable widgets (columns > 4)
        if col > 4: return
        
        path = self.file_list[row]['path']
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法播放文件: {e}")

    def on_file_right_double_click(self, row, col):
        self.open_file_folder(row)

    def show_file_context_menu(self, pos):
        item = self.file_table.itemAt(pos)
        if not item: return
        row = item.row()
        
        menu = QMenu(self)
        action_open_folder = menu.addAction("打开文件所在位置")
        
        action = menu.exec(self.file_table.mapToGlobal(pos))
        
        if action == action_open_folder:
            self.open_file_folder(row)

    def open_file_folder(self, row):
        if row < 0 or row >= len(self.file_list): return
        path = self.file_list[row]['path']
        folder = os.path.dirname(path)
        if os.path.exists(folder):
            try:
                # Use explorer /select, path to select the file
                subprocess.run(['explorer', '/select,', os.path.normpath(path)])
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法打开目录: {e}")

    def on_table_format_changed(self, widget):
        index = self.file_table.indexAt(widget.pos())
        row = index.row()
        if row < 0: return

        # Update Data
        formats = []
        if widget.chk_mp4.isChecked(): formats.append("mp4")
        if widget.chk_mkv.isChecked(): formats.append("mkv")
        
        self.file_list[row]['config']['formats'] = formats

    def on_table_quality_changed(self, widget):
        index = self.file_table.indexAt(widget.pos())
        row = index.row()
        if row < 0: return

        qualities = []
        if widget.chk_lossless.isChecked(): qualities.append("lossless")
        if widget.chk_hd.isChecked(): qualities.append("hd")
        if widget.chk_balanced.isChecked(): qualities.append("balanced")
        if widget.chk_compact.isChecked(): qualities.append("compact")
        
        self.file_list[row]['config']['qualities'] = qualities

    def on_table_rotation_changed(self, widget):
        index = self.file_table.indexAt(widget.pos())
        row = index.row()
        if row < 0: return

        rotation = widget.group.checkedId()
        self.file_list[row]['config']['rotation'] = rotation
    
    def on_table_trim_changed(self, widget):
        index = self.file_table.indexAt(widget.pos())
        row = index.row()
        if row < 0:
            return
        self.file_list[row]['config']['trim_start'] = widget.edit_start.text()
        self.file_list[row]['config']['trim_end'] = widget.edit_end.text()
    
    def on_table_stabilize_changed(self, widget):
        index = self.file_table.indexAt(widget.pos())
        row = index.row()
        if row < 0:
            return
        self.file_list[row]['config']['stabilization'] = widget.slider.value()

    def delete_selected_files(self):
        rows = sorted(set(index.row() for index in self.file_table.selectedIndexes()), reverse=True)
        for row in rows:
            self.file_table.removeRow(row)
            del self.file_list[row]
        # Re-index
        for i in range(self.file_table.rowCount()):
            self.file_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
        
        if self.file_table.rowCount() == 0:
            self.file_table.applyResizeModeEmpty()
        else:
            self.file_table.applyResizeModeWithContent()

    def clear_all_files(self):
        if not self.file_list: return
        
        # Custom Dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("确认清空")
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        
        v_layout = QVBoxLayout(dialog)
        h_layout = QHBoxLayout()
        
        icon_label = QLabel()
        icon = self.style().standardIcon(QStyle.SP_MessageBoxWarning)
        icon_label.setPixmap(icon.pixmap(16, 16))
        
        text_label = QLabel("确认清空所有待转码文件吗？")
        
        h_layout.addWidget(icon_label)
        h_layout.addWidget(text_label)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        
        v_layout.addLayout(h_layout)
        v_layout.addWidget(btn_box)
        
        # Position
        btn_pos = self.btn_clear_all.mapToGlobal(QPoint(0, 0))
        dialog.move(btn_pos.x(), btn_pos.y() - dialog.sizeHint().height() - 10)
        
        if dialog.exec() == QDialog.Accepted:
            self.file_table.setRowCount(0)
            self.file_list.clear()
            self.file_table.applyResizeModeEmpty()

    # --- Configuration Logic ---

    def get_current_global_config(self):
        # Gather current config from Global UI
        formats = []
        if self.chk_mp4.isChecked(): formats.append("mp4")
        if self.chk_mkv.isChecked(): formats.append("mkv")
        
        qualities = []
        if self.chk_lossless.isChecked(): qualities.append("lossless")
        if self.chk_hd.isChecked(): qualities.append("hd")
        if self.chk_balanced.isChecked(): qualities.append("balanced")
        if self.chk_compact.isChecked(): qualities.append("compact")
        
        rotation = self.rot_group_btn.checkedId()
        trim_start = self.edit_trim_start.text()
        trim_end = self.edit_trim_end.text()
        stabilization = self.stab_slider.value()
        
        return {
            "formats": formats,
            "qualities": qualities,
            "rotation": rotation,
            "trim_start": trim_start,
            "trim_end": trim_end,
            "stabilization": stabilization
        }

    def sync_global_formats(self):
        formats = []
        if self.chk_mp4.isChecked(): formats.append("mp4")
        if self.chk_mkv.isChecked(): formats.append("mkv")
        
        for i, file_data in enumerate(self.file_list):
            file_data['config']['formats'] = formats
            self.update_table_row(i, file_data)

    def sync_global_qualities(self):
        qualities = []
        if self.chk_lossless.isChecked(): qualities.append("lossless")
        if self.chk_hd.isChecked(): qualities.append("hd")
        if self.chk_balanced.isChecked(): qualities.append("balanced")
        if self.chk_compact.isChecked(): qualities.append("compact")
        
        for i, file_data in enumerate(self.file_list):
            file_data['config']['qualities'] = qualities
            self.update_table_row(i, file_data)

    def sync_global_rotation(self):
        rotation = self.rot_group_btn.checkedId()
        for i, file_data in enumerate(self.file_list):
            file_data['config']['rotation'] = rotation
            self.update_table_row(i, file_data)

    def sync_global_trim(self):
        trim_start = self.edit_trim_start.text()
        trim_end = self.edit_trim_end.text()
        for i, file_data in enumerate(self.file_list):
            file_data['config']['trim_start'] = trim_start
            file_data['config']['trim_end'] = trim_end
            self.update_table_row(i, file_data)

    def sync_global_stabilization(self):
        stabilization = self.stab_slider.value()
        for i, file_data in enumerate(self.file_list):
            file_data['config']['stabilization'] = stabilization
            self.update_table_row(i, file_data)

    # --- Global Config ---
    
    def toggle_output_browse(self, checked):
        self.btn_browse_out.setEnabled(checked)
        self.out_path_display.setEnabled(checked)
        
    def browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.out_path_display.setText(d)

    def update_scheduler_threads(self):
        self.scheduler.set_max_threads(self.thread_slider.value())

    # --- Task Execution ---

    def start_conversion(self):
        # Validation
        if not self.file_list:
            QMessageBox.warning(self, "提示", "请先添加视频文件")
            return
            
        # Check output dir
        output_dir_mode = "custom" if self.radio_out_custom.isChecked() else "same"
        custom_dir = self.out_path_display.text()
        
        if output_dir_mode == "custom":
            if not custom_dir or not os.path.isdir(custom_dir):
                 QMessageBox.warning(self, "提示", "请选择有效的自定义输出目录")
                 return
                 
        # Generate Tasks
        new_tasks = []
        
        for row, file_data in enumerate(self.file_list):
            src_path = file_data['path']
            src_dir = os.path.dirname(src_path)
            src_name = os.path.splitext(file_data['name'])[0]
            out_base_dir = custom_dir if output_dir_mode == "custom" else src_dir
            widget_f = self.file_table.cellWidget(row, 5)
            widget_q = self.file_table.cellWidget(row, 6)
            widget_r = self.file_table.cellWidget(row, 7)
            widget_t = self.file_table.cellWidget(row, 8)
            widget_s = self.file_table.cellWidget(row, 9)
            formats = []
            qualities = []
            if widget_f and getattr(widget_f, "chk_mp4", None) and widget_f.chk_mp4.isChecked(): formats.append("mp4")
            if widget_f and getattr(widget_f, "chk_mkv", None) and widget_f.chk_mkv.isChecked(): formats.append("mkv")
            if widget_q and getattr(widget_q, "chk_lossless", None) and widget_q.chk_lossless.isChecked(): qualities.append("lossless")
            if widget_q and getattr(widget_q, "chk_hd", None) and widget_q.chk_hd.isChecked(): qualities.append("hd")
            if widget_q and getattr(widget_q, "chk_balanced", None) and widget_q.chk_balanced.isChecked(): qualities.append("balanced")
            if widget_q and getattr(widget_q, "chk_compact", None) and widget_q.chk_compact.isChecked(): qualities.append("compact")
            if not formats or not qualities:
                continue
            rotation = widget_r.group.checkedId() if widget_r and getattr(widget_r, "group", None) else 0
            trim_start = widget_t.edit_start.text() if widget_t and getattr(widget_t, "edit_start", None) else "0"
            trim_end = widget_t.edit_end.text() if widget_t and getattr(widget_t, "edit_end", None) else "0"
            stabilization = widget_s.slider.value() if widget_s and getattr(widget_s, "slider", None) else 0
            for fmt in formats:
                for quality in qualities:
                    # Map quality to params
                    preset = "medium"
                    crf = 23
                    quality_suffix = "Balanced"
                    
                    if quality == "lossless":
                        crf = 0
                        preset = "ultrafast"
                        quality_suffix = "Lossless"
                    elif quality == "hd":
                        crf = 18
                        preset = "fast"
                        quality_suffix = "HD"
                    elif quality == "compact":
                        crf = 28
                        preset = "slow"
                        quality_suffix = "Compact"
                        
                    # Filename: name_quality.fmt
                    out_name = f"{src_name}_{quality_suffix}.{fmt}"
                    out_path = os.path.join(out_base_dir, out_name)
                    
                    task_id = str(uuid.uuid4())
                    
                    task = TranscodeTask(
                        task_id, src_path, out_path, fmt, quality,
                        rotation, trim_start, trim_end,
                        stabilization, preset, crf
                    )
                    new_tasks.append(task)

        if not new_tasks:
            QMessageBox.warning(self, "提示", "未生成有效任务，请检查格式和质量选择")
            return

        # UI Update
        self.btn_start.setEnabled(False)
        self.btn_start.setText("转码中...")
        self.btn_cancel_all.setEnabled(True)
        self.btn_pause.setVisible(True)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("暂停任务")
        self.file_group.setEnabled(False) # Lock file inputs
        
        # Add to Task Table and Schedule
        for task in new_tasks:
            self.add_task_to_table(task)
            
            # Create signals
            signals = WorkerSignals()
            signals.progress.connect(self.on_task_progress)
            signals.status_changed.connect(self.on_task_status)
            signals.finished.connect(self.on_task_finished)
            signals.error.connect(self.on_task_error)
            
            self.tasks[task.task_id] = task
            self.scheduler.start_task(task, signals)

    def add_task_to_table(self, task):
        row = self.task_table.rowCount()
        self.task_table.insertRow(row)
        
        # Store row index in task? No, store task_id in table item data
        item_id = QTableWidgetItem(str(row + 1))
        item_id.setData(Qt.UserRole, task.task_id)
        
        self.task_table.setItem(row, 0, item_id)
        self.task_table.setItem(row, 1, QTableWidgetItem(os.path.basename(task.output_path)))
        self.task_table.setItem(row, 2, QTableWidgetItem(task.source_path))
        self.task_table.setItem(row, 3, QTableWidgetItem(task.output_path))
        self.task_table.setItem(row, 4, QTableWidgetItem("0%"))
        self.task_table.setItem(row, 5, QTableWidgetItem(TaskStatus.WAITING))

        if self.btn_scroll_follow.isChecked():
            self.task_table.scrollToBottom()

    def get_row_by_task_id(self, task_id):
        for r in range(self.task_table.rowCount()):
            item = self.task_table.item(r, 0)
            if item and item.data(Qt.UserRole) == task_id:
                return r
        return -1

    @Slot(str, int)
    def on_task_progress(self, task_id, percent):
        row = self.get_row_by_task_id(task_id)
        if row >= 0:
            self.task_table.setItem(row, 4, QTableWidgetItem(f"{percent}%"))

    @Slot(str, str)
    def on_task_status(self, task_id, status):
        # Update data model
        if task_id in self.tasks:
            self.tasks[task_id].status = status
            
        row = self.get_row_by_task_id(task_id)
        if row >= 0:
            self.task_table.setItem(row, 5, QTableWidgetItem(status))

    @Slot(str)
    def on_task_finished(self, task_id):
        self.on_task_status(task_id, TaskStatus.COMPLETED)
        self.on_task_progress(task_id, 100)
        self.check_all_finished()

    @Slot(str, str)
    def on_task_error(self, task_id, error_msg):
        self.on_task_status(task_id, TaskStatus.FAILED)
        # Maybe show tooltip?
        row = self.get_row_by_task_id(task_id)
        if row >= 0:
            self.task_table.item(row, 5).setToolTip(error_msg)
        self.check_all_finished()

    def check_all_finished(self):
        # Check if any running
        # If scheduler pool is empty?
        # Simple check:
        # self.scheduler.pool.activeThreadCount() > 0? No, that's immediate.
        # We should check our task statuses.
        
        # But for UI state:
        # If all tasks in list are Done/Failed/Cancelled -> Reset UI
        
        all_done = True
        for task in self.tasks.values():
            if task.status in [TaskStatus.WAITING, TaskStatus.RUNNING]:
                all_done = False
                break
        
        if all_done:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("开始转换")
            self.btn_cancel_all.setEnabled(False)
            self.btn_pause.setVisible(False)
            self.file_group.setEnabled(True)

    def toggle_pause(self):
        if self.scheduler.is_paused:
            self.scheduler.resume_all()
            self.btn_pause.setText("暂停任务")
        else:
            self.scheduler.pause_all()
            self.btn_pause.setText("继续任务")

    def clear_task_list(self):
        def show_popup(text, is_warning=True):
            dialog = QDialog(self)
            dialog.setWindowTitle("提示")
            dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
            
            v_layout = QVBoxLayout(dialog)
            h_layout = QHBoxLayout()
            
            icon_label = QLabel()
            icon = self.style().standardIcon(QStyle.SP_MessageBoxWarning if is_warning else QStyle.SP_MessageBoxQuestion)
            icon_label.setPixmap(icon.pixmap(16, 16))
            
            text_label = QLabel(text)
            
            h_layout.addWidget(icon_label)
            h_layout.addWidget(text_label)
            
            if is_warning:
                btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
            else:
                btn_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
            
            btn_box.accepted.connect(dialog.accept)
            btn_box.rejected.connect(dialog.reject)
            
            v_layout.addLayout(h_layout)
            v_layout.addWidget(btn_box)
            
            dialog.adjustSize()
            btn_pos = self.btn_clear_tasks.mapToGlobal(QPoint(0, 0))
            dialog.move(btn_pos.x(), btn_pos.y() - dialog.height() - 5)
            
            return dialog.exec()

        # Check if any running or paused
        if any(t.status == TaskStatus.RUNNING for t in self.tasks.values()):
            show_popup("有任务正在进行中，无法清空列表。\n请先取消或等待完成。")
            return
        
        # Double check with scheduler active workers
        if self.scheduler.active_workers:
            show_popup("后台仍有活动任务，无法清空。")
            return

        # Custom Dialog for Clear Confirmation
        if show_popup("确认清空任务列表吗？", is_warning=False) == QDialog.Accepted:
            self.tasks.clear()
            self.task_table.setRowCount(0)

    def on_task_double_click(self, row, col):
        item = self.task_table.item(row, 0)
        if not item: return
        task_id = item.data(Qt.UserRole)
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status == TaskStatus.COMPLETED:
                if os.path.exists(task.output_path):
                    try:
                        os.startfile(task.output_path)
                    except Exception as e:
                        QMessageBox.warning(self, "错误", f"无法打开文件: {e}")
                else:
                    QMessageBox.warning(self, "错误", "文件不存在")

    def on_task_right_double_click(self, row, col):
        self.open_task_folder(row)

    def open_task_folder(self, row):
        item = self.task_table.item(row, 0)
        if not item: return
        task_id = item.data(Qt.UserRole)
        if task_id in self.tasks:
            task = self.tasks[task_id]
            folder = os.path.dirname(task.output_path)
            if os.path.exists(folder):
                # Select file in explorer
                try:
                    subprocess.run(['explorer', '/select,', os.path.normpath(task.output_path)])
                except Exception as e:
                    QMessageBox.warning(self, "错误", f"无法打开目录: {e}")
            else:
                QMessageBox.warning(self, "错误", "目录不存在")

    def show_task_context_menu(self, pos):
        item = self.task_table.itemAt(pos)
        if not item: return
        row = item.row()
        
        menu = QMenu(self)
        action_open_folder = menu.addAction("打开文件所在位置")
        
        action = menu.exec(self.task_table.mapToGlobal(pos))
        
        if action == action_open_folder:
            self.open_task_folder(row)

    def cancel_all_tasks(self):
        self.scheduler.cancel_all()
        # Update UI
        for task in self.tasks.values():
            if task.status in [TaskStatus.WAITING, TaskStatus.RUNNING]:
                task.status = TaskStatus.CANCELLED
                self.on_task_status(task.task_id, TaskStatus.CANCELLED)
        
        self.check_all_finished()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Modern Style
    app.setStyle("Fusion")
    
    window = ShenmaConverter()
    window.show()
    sys.exit(app.exec())
