"""
count_notes_comment.py
用于 Phigros 的官谱分析器

除了本文档字符串，本程序其余所有注释均由 AI 生成。
代码是我自己写的。
"""

from __future__ import annotations
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from json import load, JSONDecodeError
from shutil import copy2
from pathlib import Path
from threading import Thread, Event, Lock
from itertools import cycle
from time import perf_counter
from argparse import ArgumentParser, Namespace
from enum import Enum


class CountErrorCode(Enum):
    """统计错误码枚举"""

    JsonDecodeError = 1  # JSON 解析错误
    FileNotFoundError = 2  # 文件未找到
    PermissionError = 3  # 权限不足
    UnicodeDecodeError = 4  # UTF-8 解码错误
    FieldNotExistError = 5  # 必要字段缺失


# ===================== 核心统计函数 =====================
def count(file: str) -> tuple[str, int, float] | CountErrorCode:
    """
    解析单个 Phigros 谱面 JSON 文件，返回 (文件路径, 音符总数, BPM)
    若出错则返回对应的错误码枚举
    """
    try:
        with open(file, "r", encoding="utf-8") as f:
            data = load(f)
    except JSONDecodeError:
        return CountErrorCode.JsonDecodeError
    except FileNotFoundError:
        return CountErrorCode.FileNotFoundError
    except PermissionError:
        return CountErrorCode.PermissionError
    except UnicodeDecodeError:
        return CountErrorCode.UnicodeDecodeError

    try:
        # 统计所有判定线上的 notesAbove 和 notesBelow 总数
        notes = sum(
            (len(l["notesAbove"]) + len(l["notesBelow"]) for l in data["judgeLineList"])
        )
        bpm = data["judgeLineList"][0]["bpm"]  # 取第一条判定线的 BPM
    except KeyError:
        return CountErrorCode.FieldNotExistError

    return file, notes, float(bpm)


# ===================== 重命名 & 复制 =====================
def rename(file: str, output: Path) -> None:
    """
    对单个文件：获取音符数和 BPM，识别难度，构造新文件名，复制到目标文件夹
    """
    result = count(file)
    if isinstance(result, CountErrorCode):
        match result:
            case CountErrorCode.JsonDecodeError:
                print(f"ERROR: 文件 {file!r} 无法解析为 JSON")
                return
            case CountErrorCode.FileNotFoundError:
                print(f"ERROR: 文件 {file!r} 不存在")
                return
            case CountErrorCode.PermissionError:
                print(f"ERROR: 没有足够的权限读取文件 {file!r}")
                return
            case CountErrorCode.UnicodeDecodeError:
                print(f"ERROR: 文件 {file!r} 无法按 UTF-8 解码")
                return
            case CountErrorCode.FieldNotExistError:
                print(f"ERROR: 文件 {file!r} 不是有效的谱面文件")
                return

    # 难度识别（按优先级顺序匹配文件名中的关键词）
    if "EZ" in file:
        difficult = "EZ"
    elif "HD" in file:
        difficult = "HD"
    elif "IN" in file:
        difficult = "IN"
    elif "AT" in file:
        difficult = "AT"
    elif "Legacy" in file:
        difficult = "Legacy"
    else:
        difficult = "Unknown"

    # 如果文件名包含 "Error"，在难度后追加标记（方便区分错误谱面）
    if "Error" in file:
        difficult += "_Error"

    _, notes, bpm = result

    file_name = f"Chart_{difficult}_{notes}_{bpm}.json"

    try:
        copy2(file, output / file_name)  # copy2 保留原始元数据（如修改时间）
    except PermissionError:
        print(f"ERROR: 没有足够的权限写入 {str(output)}")
        return


# ===================== 并行处理主控 =====================
def run(src: Path, output: Path, workers: int | None) -> None:
    """
    使用多进程处理 src 目录下的所有文件，将结果复制到 output
    workers: 进程数，None 表示使用 CPU 核心数
    """
    files = [str(f) for f in src.glob("*")]  # 获取源目录下所有文件（不递归子目录）
    executor = ProcessPoolExecutor(workers)
    real_workers = executor._max_workers  # type: ignore[attr-defined]

    # ---------- 动画线程函数 ----------
    def spining(event: Event, lock: Lock) -> None:
        """
        后台线程：每 0.1 秒检查一次 event，未结束时打印旋转光标和当前进度
        """
        for c in cycle(r"\|/-"):  # 旋转字符序列
            with lock:
                print(f"运行中... ({done:4}/{len(files):4}) {c}", end="\r")
            if event.wait(0.1):  # 等待 0.1 秒，若 event 被设置则退出
                print(f"运行中... ({done:4}/{len(files):4}) 完成")
                break

    event = Event()  # 用于通知动画线程结束
    lock = Lock()  # 保护共享变量 done
    done = 0  # 已完成的任务数（由主线程更新，动画线程只读）
    spin = Thread(target=spining, args=(event, lock))

    print(f"正在使用 {real_workers} 个进程处理 {len(files)} 个文件...")
    t0 = perf_counter()
    spin.start()

    with executor:
        futures = []
        # 提交所有任务
        for f in files:
            future = executor.submit(rename, f, output)
            futures.append(future)

        # 每完成一个任务，增加 done 计数
        for _ in as_completed(futures):
            with lock:
                done += 1

    # 通知动画线程结束并等待它退出
    event.set()
    spin.join()

    t0 = perf_counter() - t0
    print(f"处理完成 {len(files)} 个文件，耗时 {t0:9.6f} 秒。")


# ===================== 路径检查辅助函数 =====================
def _check(
    path: Path, dir: bool, exist: bool = True, strict: bool = False, create: bool = True
) -> bool:
    """
    检查路径是否存在、是否为目录/文件
    dir: True 期望是目录，False 期望是文件
    exist: True 期望路径存在，False 期望不存在（本程序未使用 False 情况）
    strict: True 时若检查失败直接抛出异常，False 时返回布尔值
    create: 当路径不存在且 strict=False 时，是否自动创建（目录则创建目录，文件则创建空文件）
    """
    if exist:
        if not path.exists():
            if strict:
                raise FileNotFoundError(f"{str(path)} 不存在")
            if create:
                if dir:
                    path.mkdir(parents=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                return True
            return False
    if dir:
        if not path.is_dir():
            if strict:
                raise FileExistsError(f"{str(path)} 不是文件夹，但期望是文件夹")
            return False
    else:
        if path.is_dir():
            if strict:
                raise FileNotFoundError(f"{str(path)} 不是文件，但期望是文件")
            return False
    return True


def _arg_parser() -> Namespace:
    """构建命令行参数解析器"""
    ap = ArgumentParser(
        prog="Phigros官谱分析器",
        description="一个计算谱面文件音符数量和 BPM，并自动复制后重命名的命令行工具",
    )
    ap.add_argument("source-folder", help="原谱面文件存放文件夹")
    ap.add_argument("save-folder", help="处理后谱面文件的存放文件夹")
    ap.add_argument(
        "process-number",
        nargs="?",
        help="程序使用的进程数目（留空使用 CPU 核心数目）",
        type=int,
        default=None,
    )
    return ap.parse_args()


# ===================== 命令行入口 =====================
def main():
    args = _arg_parser()
    src = Path(args.source_folder)
    out = Path(args.save_folder)
    _check(src, True, strict=True)  # 源目录必须存在且为目录
    _check(
        out, True, strict=True, create=True
    )  # 目标目录必须存在且为目录（会自动创建）

    run(src, out, args.process_number)


if __name__ == "__main__":
    main()
