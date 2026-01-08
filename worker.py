import os
import subprocess
import re
import time
import psutil
from utils import get_ffmpeg_path
from PySide6.QtCore import QObject, QThread, Signal, QRunnable, QThreadPool, QMutex, QMutexLocker

class TaskStatus:
    WAITING = "等待中"
    RUNNING = "转码中"
    COMPLETED = "已完成"
    FAILED = "转码失败"
    CANCELLED = "已取消"

class TranscodeTask:
    def __init__(self, task_id, source_path, output_path, fmt, quality, rotation, trim_start, trim_end, stabilization, preset, crf):
        self.task_id = task_id
        self.source_path = source_path
        self.output_path = output_path
        self.fmt = fmt
        self.quality = quality
        self.rotation = rotation
        self.trim_start = trim_start
        self.trim_end = trim_end
        self.stabilization = stabilization # 0-100
        self.preset = preset
        self.crf = crf
        self.status = TaskStatus.WAITING
        self.progress = 0
        self.error_msg = ""

class WorkerSignals(QObject):
    progress = Signal(str, int) # task_id, percentage
    status_changed = Signal(str, str) # task_id, new_status
    finished = Signal(str) # task_id
    error = Signal(str, str) # task_id, error_msg
    log = Signal(str, str) # task_id, log_line

class Worker(QRunnable):
    def __init__(self, task, signals):
        super().__init__()
        self.task = task
        self.signals = signals
        self.is_cancelled = False
        self.process = None

    def get_duration(self, file_path):
        """Get video duration in seconds using ffprobe or ffmpeg"""
        try:
            # We use ffmpeg -i because we might not have ffprobe, but checking is safer
            # Actually prompt said "ffmpeg.exe process call", didn't explicitly say ffprobe is there.
            # We can use ffmpeg -i input.mp4 and parse stderr.
            cmd = [get_ffmpeg_path(), "-i", file_path]
            # Fix UnicodeDecodeError by enforcing utf-8 and ignore errors
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                encoding='utf-8', 
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.stderr:
                # Duration: 00:00:05.12, start: ...
                match = re.search(r"Duration:\s+(\d{2}):(\d{2}):(\d{2}\.\d+)", result.stderr)
                if match:
                    hours, minutes, seconds = match.groups()
                    return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        except Exception as e:
            print(f"Error getting duration: {e}")
        return 0

    def parse_time(self, time_str):
        # time=00:00:05.12
        try:
            parts = time_str.split(':')
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        except:
            return 0

    def run(self):
        if self.is_cancelled:
            return

        self.signals.status_changed.emit(self.task.task_id, TaskStatus.RUNNING)
        
        # 0. Prepare
        input_file = self.task.source_path
        output_file = self.task.output_path
        
        # Ensure output dir exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # 1. Stabilization (Two pass)
        trf_file = os.path.join(os.path.dirname(output_file), f"{self.task.task_id}_stab.trf").replace('\\', '/')
        
        if self.task.stabilization > 0:
            # Pass 1
            # Escape : in path for filter syntax if needed, but usually simple quotes work if no special chars
            # Windows paths with : (C:/...) might be an issue in filter chain if not escaped correctly
            # ffmpeg syntax: result='C\:/path/to/file.trf'
            trf_file_escaped = trf_file.replace(':', '\\:')
            
            cmd_pass1 = [
                get_ffmpeg_path(), "-y", "-i", input_file,
                "-vf", f"vidstabdetect=result='{trf_file_escaped}'",
                "-f", "null", "-"
            ]
            
            if not self.run_subprocess(cmd_pass1, parse_progress=True, duration_override=None, phase="Stabilization Analysis"):
                return # Failed or Cancelled

        # 2. Main Encoding Command Construction
        # Filters
        filters = []
        
        # Stabilization Transform (if enabled)
        if self.task.stabilization > 0:
            trf_file_escaped = trf_file.replace(':', '\\:')
            filters.append(f"vidstabtransform=input='{trf_file_escaped}':smoothing={self.task.stabilization}")

        # Rotation
        if self.task.rotation == 1: # Left 90 (Transpose=2)
            filters.append("transpose=2")
        elif self.task.rotation == 2: # Right 90 (Transpose=1)
            filters.append("transpose=1")
        elif self.task.rotation == 3: # 180
            filters.append("transpose=2,transpose=2") # Or rotate=PI, but transpose is often faster/simpler for 90/180

        # Trim (Use -ss and -to/t input options or filter? -ss before -i is faster)
        # Requirement: "Start X seconds, End Y seconds (from end)". 
        # "Right input box means end count down seconds". e.g. "5" means stop 5s before end.
        # This requires knowing duration.
        total_duration = self.get_duration(input_file)
        if total_duration == 0:
             # Fallback if duration unknown, can't do "end minus X" easily without complex filter or duration check.
             # We will proceed assuming 0 means full if duration fail.
             pass
        
        start_time = float(self.task.trim_start) if self.task.trim_start else 0
        end_minus = float(self.task.trim_end) if self.task.trim_end else 0
        
        # Construct command
        cmd = [get_ffmpeg_path(), "-y"] # -y overwrite
        
        # Seek (Input seeking is fast)
        if start_time > 0:
            cmd.extend(["-ss", str(start_time)])
            
        cmd.extend(["-i", input_file])
        
        # Output duration limit (if trimming end)
        if end_minus > 0 and total_duration > 0:
            duration_to_keep = total_duration - start_time - end_minus
            if duration_to_keep > 0:
                cmd.extend(["-t", str(duration_to_keep)])

        # Video Codec & Quality
        if self.task.fmt == "mp4":
            cmd.extend(["-c:v", "libx264", "-c:a", "aac"])
        elif self.task.fmt == "mkv":
            cmd.extend(["-c:v", "libx264", "-c:a", "aac"]) # Or copy if no re-encode needed? Requirement says "compress options", so re-encode.
        
        cmd.extend(["-crf", str(self.task.crf), "-preset", self.task.preset])

        # Filters apply
        if filters:
            cmd.extend(["-vf", ",".join(filters)])
        
        cmd.append(output_file)

        # 3. Run Main Encoding
        success = self.run_subprocess(cmd, parse_progress=True, total_duration=total_duration, phase="Encoding")
        
        # Cleanup
        if self.task.stabilization > 0:
            if os.path.exists(trf_file):
                try:
                    os.remove(trf_file)
                except:
                    pass

        if success:
            self.signals.finished.emit(self.task.task_id)
        else:
            if not self.is_cancelled:
                self.signals.error.emit(self.task.task_id, "Process failed or returned error")

    def run_subprocess(self, cmd, parse_progress=False, total_duration=0, duration_override=None, phase=""):
        if self.is_cancelled: return False
        
        # Fix for windows no window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        try:
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Parse output
            for line in self.process.stdout:
                if self.is_cancelled:
                    self.process.kill()
                    return False
                
                self.signals.log.emit(self.task.task_id, line.strip())
                
                if parse_progress:
                    # frame=  123 fps=... time=00:00:05.12 bitrate=...
                    time_match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d+)", line)
                    if time_match and total_duration > 0:
                        current_time = self.parse_time(time_match.group(1))
                        percent = int((current_time / total_duration) * 100)
                        if percent > 100: percent = 100
                        self.signals.progress.emit(self.task.task_id, percent)
            
            self.process.wait()
            return self.process.returncode == 0
        except Exception as e:
            self.signals.error.emit(self.task.task_id, str(e))
            return False

    def cancel(self):
        self.is_cancelled = True
        if self.process:
            try:
                self.process.kill()
            except:
                pass

    def pause(self):
        if self.process:
            try:
                p = psutil.Process(self.process.pid)
                p.suspend()
            except Exception as e:
                print(f"Error pausing process: {e}")

    def resume(self):
        if self.process:
            try:
                p = psutil.Process(self.process.pid)
                p.resume()
            except Exception as e:
                print(f"Error resuming process: {e}")

class Scheduler(QObject):
    def __init__(self, max_threads=3):
        super().__init__()
        self.pool = QThreadPool()
        self.set_max_threads(max_threads)
        self.active_workers = {} # task_id -> worker
        self.is_paused = False

    def set_max_threads(self, n):
        self.pool.setMaxThreadCount(n)

    def start_task(self, task, signals):
        worker = Worker(task, signals)
        self.active_workers[task.task_id] = worker
        
        # Connect signals to cleanup
        # We need to hook into finished/error to remove from active_workers
        # But signals are connected in main.py. 
        # We can wrap the signals or rely on main.py to call a cleanup method.
        # Better: let main.py notify scheduler when task is done, 
        # OR connect here if we pass a callback or proxy signal.
        # Since WorkerSignals is passed in, we can connect to it.
        signals.finished.connect(lambda tid=task.task_id: self.remove_worker(tid))
        signals.error.connect(lambda tid, err: self.remove_worker(tid))
        
        self.pool.start(worker)
        if self.is_paused:
             # If tasks are added while paused? The requirement says "pause running tasks".
             # Queue management is handled by QThreadPool. We can't easily pause "queued" tasks other than not starting them.
             # But QThreadPool starts them automatically.
             # For now, we implement pause/resume for active workers.
             pass

    def remove_worker(self, task_id):
        if task_id in self.active_workers:
            del self.active_workers[task_id]

    def cancel_all(self):
        self.is_paused = False
        for worker in self.active_workers.values():
            worker.cancel()
        self.pool.clear() # Clear waiting tasks
        self.active_workers.clear()

    def pause_all(self):
        self.is_paused = True
        for worker in self.active_workers.values():
            worker.pause()

    def resume_all(self):
        self.is_paused = False
        for worker in self.active_workers.values():
            worker.resume()
