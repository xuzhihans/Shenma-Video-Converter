import os
import subprocess
import sys
import time
import shutil

def build():
    # 0. Clean previous build artifacts
    print("清理旧的构建文件...")
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            try:
                # Don't delete dist completely, just the target exe if needed, 
                # but removing build is safer for clean builds.
                # Here we just rely on PyInstaller's --clean
                pass
            except Exception:
                pass

    # 1. Check for ffmpeg.exe
    if not os.path.exists("ffmpeg.exe"):
        print("错误: 当前目录下未找到 ffmpeg.exe")
        print("请将 ffmpeg.exe 复制到项目根目录 (与 main.py 同级) 后重试。")
        input("按回车键退出...")
        return

    # 2. Check/Install Dependencies (PyInstaller, Pillow)
    required_packages = ["pyinstaller", "pillow"]
    for package in required_packages:
        try:
            __import__(package if package != "pillow" else "PIL")
        except ImportError:
            print(f"正在安装 {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            except Exception as e:
                print(f"安装 {package} 失败: {e}")
                return

    # 3. Run PyInstaller
    print("开始打包...")
    # --noconsole (or --windowed) 隐藏控制台
    # --onefile 打包成单文件
    # --add-binary "src;dest" 添加二进制文件
    # --clean 清理缓存
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--clean",
        "--name", "神马转码器",
        "--add-binary", "ffmpeg.exe;.",
        "main.py"
    ]

    # Check for icon
    if os.path.exists("icon.ico"):
        cmd.insert(-1, "--icon=icon.ico")
        # Add icon as data file for runtime use (window icon)
        cmd.insert(-1, "--add-data=icon.ico;.")
    else:
        print("提示: 未找到 icon.ico，将使用默认图标。")
        print("若需自定义图标，请将 .ico 文件重命名为 icon.ico 并放在项目根目录。")
    
    try:
        subprocess.check_call(cmd)
        
        # Rename to avoid icon cache issues
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target_name = f"神马转码器_{timestamp}.exe"
        original_path = os.path.join("dist", "神马转码器.exe")
        new_path = os.path.join("dist", target_name)
        
        if os.path.exists(original_path):
            if os.path.exists(new_path):
                os.remove(new_path)
            os.rename(original_path, new_path)
            
        print("\n" + "="*30)
        print("打包成功！")
        print(f"可执行文件位于: {new_path}")
        print("注意：文件名已添加时间戳以避免图标缓存问题。")
        print("="*30)
    except subprocess.CalledProcessError as e:
        print(f"打包过程中出错: {e}")

    input("按回车键退出...")

if __name__ == "__main__":
    build()
