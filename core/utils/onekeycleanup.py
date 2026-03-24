import os
import glob
from core._1_ytdlp import find_video_files
import shutil

def cleanup(history_dir="static/history"):
    """
    清理临时文件并将视频相关文件归档到历史记录目录中。
    如果历史记录目录中已存在同名文件夹，则会自动在原视频名称开头添加递增数字前缀（如：1_原视频名称, 2_原视频名称）以避免覆盖。

    参数:
        history_dir (str): 历史记录的根目录路径，默认为 "static/history"。

    返回:
        None

    异常:
        可能抛出文件系统操作相关的 OSError 或 PermissionError，但在移动和删除文件时已做容错处理。
    """
    # 获取视频文件名
    video_file = find_video_files()
    video_name = video_file.split("/")[1]
    video_name = os.path.splitext(video_name)[0]
    video_name = sanitize_filename(video_name)
    
    # 创建基础历史目录
    os.makedirs(history_dir, exist_ok=True)
    
    # 处理文件夹同名情况，避免重复覆盖
    base_video_name = video_name
    video_history_dir = os.path.join(history_dir, video_name)
    counter = 1
    while os.path.exists(video_history_dir):
        video_name = f"{counter}_{base_video_name}"
        video_history_dir = os.path.join(history_dir, video_name)
        counter += 1

    # 创建视频专属历史记录目录及子目录
    log_dir = os.path.join(video_history_dir, "log")
    gpt_log_dir = os.path.join(video_history_dir, "gpt_log")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(gpt_log_dir, exist_ok=True)

    # 移动非日志文件
    for file in glob.glob("static/output/*"):
        if not file.endswith(('log', 'gpt_log', 'audio')):
            move_file(file, video_history_dir)

    # 移动日志文件
    for file in glob.glob("static/output/log/*"):
        move_file(file, log_dir)

    # 移动gpt日志文件
    for file in glob.glob("static/output/gpt_log/*"):
        move_file(file, gpt_log_dir)

    # 删除空的输出目录
    try:
        os.rmdir("static/output/log")
        os.rmdir("static/output/gpt_log")
        os.rmdir("static/output")
    except OSError:
        pass  # 忽略删除目录时的错误

def move_file(src, dst):
    """
    移动文件或文件夹到目标目录，若目标目录已存在同名文件或文件夹，则进行覆盖。
    如果移动失败（如权限问题），会尝试复制后删除源文件作为后备方案。

    参数:
        src (str): 源文件或文件夹的路径。
        dst (str): 目标文件夹的路径。

    返回:
        None

    异常:
        内部捕获了 PermissionError 和 Exception 并在控制台打印错误信息，不会向上抛出。
    """
    try:
        # 获取源文件名
        src_filename = os.path.basename(src)
        # 使用 os.path.join 确保路径正确并包含文件名
        dst = os.path.join(dst, sanitize_filename(src_filename))
        
        if os.path.exists(dst):
            if os.path.isdir(dst):
                # 如果目标是文件夹，尝试删除其内容
                shutil.rmtree(dst, ignore_errors=True)
            else:
                # 如果目标是文件，尝试删除它
                os.remove(dst)
        
        shutil.move(src, dst, copy_function=shutil.copy2)
        print(f"✅ Moved: {src} -> {dst}")
    except PermissionError:
        print(f"⚠️ Permission error: Cannot delete {dst}, attempting to overwrite")
        try:
            shutil.copy2(src, dst)
            os.remove(src)
            print(f"✅ Copied and deleted source file: {src} -> {dst}")
        except Exception as e:
            print(f"❌ Move failed: {src} -> {dst}")
            print(f"Error message: {str(e)}")
    except Exception as e:
        print(f"❌ Move failed: {src} -> {dst}")
        print(f"Error message: {str(e)}")

def sanitize_filename(filename):
    """
    清理文件名，将不合法字符（如：<>:"/\\|?*）替换为下划线，以确保在各个操作系统上路径合法。

    参数:
        filename (str): 原始文件名。

    返回:
        str: 清理后的合法文件名。
    """
    # 移除或替换不允许的字符
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

if __name__ == "__main__":
    cleanup()