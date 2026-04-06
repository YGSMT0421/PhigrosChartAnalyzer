"""
count_notes_comment.py
用于 Phigros 的官谱分析器

除了本文档字符串，本程序其余所有注释均由 AI 生成。
代码是我自己写的。
"""

from __future__ import annotations
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
    """统计错误码枚举，用于标识解析谱面文件时可能出现的各类错误"""

    JsonDecodeError = 1  # JSON 格式解析失败
    FileNotFoundError = 2  # 文件不存在
    PermissionError = 3  # 无读写取权限
    UnicodeDecodeError = 4  # UTF-8 解码失败
    FieldNotExistError = (
        5  # 谱面必要字段缺失（judgeLineList/notesAbove/notesBelow/bpm）
    )


# ===================== 核心统计函数 =====================
def count(file: str) -> tuple[str, int, float] | CountErrorCode:
    """
    解析单个 Phigros 谱面 JSON 文件，统计音符总数和 BPM。

    参数：
        file: 谱面文件的路径（字符串形式）

    返回值：
        成功时返回一个三元组 (文件路径, 音符总数, BPM)；
        失败时返回对应的 CountErrorCode 枚举成员。

    异常：
        本函数内部捕获并处理所有预期异常，不会向外抛出。
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
        # 遍历所有判定线，累加每条判定线上 notesAbove 和 notesBelow 的音符数量
        notes = sum(
            (len(l["notesAbove"]) + len(l["notesBelow"]) for l in data["judgeLineList"])
        )
        bpm = data["judgeLineList"][0][
            "bpm"
        ]  # 约定取第一条判定线的 BPM 作为整个谱面的 BPM
    except KeyError:
        return CountErrorCode.FieldNotExistError

    return file, notes, float(bpm)


# ===================== 重命名 & 复制 =====================
def rename(file: str) -> str | CountErrorCode:
    """
    根据谱面内容生成新的文件名，并返回新文件名（不执行实际复制操作）。

    处理流程：
        1. 调用 count() 获取音符数和 BPM；
        2. 根据原文件名中的关键词识别难度（EZ/HD/IN/AT/Legacy）；
        3. 若文件名包含 "Error"，则在难度后追加 "_Error" 标记；
        4. 组装新文件名：Chart_{难度}_{音符数}_{BPM}.json。

    参数：
        file: 原始谱面文件路径

    返回值：
        成功时返回新文件名字符串，失败时返回 CountErrorCode。

    注意：
        本函数不进行文件 IO 操作，仅生成名字。
    """
    result = count(file)
    if isinstance(result, CountErrorCode):
        match result:
            case CountErrorCode.JsonDecodeError:
                print(f"ERROR: 文件 {file!r} 无法解析为 JSON")
            case CountErrorCode.FileNotFoundError:
                print(f"ERROR: 文件 {file!r} 不存在")
            case CountErrorCode.PermissionError:
                print(f"ERROR: 没有足够的权限读取文件 {file!r}")
            case CountErrorCode.UnicodeDecodeError:
                print(f"ERROR: 文件 {file!r} 无法按 UTF-8 解码")
            case CountErrorCode.FieldNotExistError:
                print(f"ERROR: 文件 {file!r} 不是有效的谱面文件")
            case _:
                raise RuntimeError(f"意外的结果：{result}")
        return result

    # 难度识别：按优先级顺序匹配文件名中的关键词
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

    # 若文件名包含 "Error"，在难度后追加标记，方便区分《望影の方舟Six》的错误谱面
    if "Error" in file:
        difficult += "_Error"

    _, notes, bpm = result

    return f"Chart_{difficult}_{notes}_{bpm}.json"


def rename_and_copy(file, output: Path) -> None:
    """
    对单个文件执行“重命名并复制”操作。

    流程：
        1. 调用 rename() 获得新文件名；
        2. 若 rename() 返回错误码（而非字符串），则直接返回；
        3. 使用 copy2 将原文件复制到目标目录下，并赋予新文件名。

    参数：
        file:   原始文件路径（字符串或 PathLike）
        output: 目标目录（Path 对象）

    异常：
        若目标目录无写入权限，捕获 PermissionError 并打印错误信息。
    """
    file_name = rename(file)
    if not isinstance(file_name, str):
        return
    try:
        copy2(file, output / file_name)  # copy2 会保留原始文件的元数据（如修改时间）
    except PermissionError:
        print(f"ERROR: 没有足够的权限写入 {str(output)}")
        return


# ===================== 并行处理主控 =====================
def run(src: Path, output: Path, workers: int | None) -> None:
    """
    使用多进程并行处理 src 目录下的所有文件，将结果复制到 output 目录。

    工作流程：
        1. 收集 src 目录下所有文件（非递归，仅当前层级）；
        2. 创建进程池，提交每个文件的 rename_and_copy 任务；
        3. 启动一个后台动画线程，实时显示处理进度；
        4. 等待所有任务完成，输出总耗时。

    参数：
        src:     源目录（必须存在且为目录）
        output:  目标目录（若不存在会自动创建）
        workers: 进程池大小，None 表示使用 CPU 核心数
    """
    files = [str(f) for f in src.glob("*")]  # 获取源目录下所有文件（不递归子目录）
    executor = ProcessPoolExecutor(workers)
    real_workers = executor._max_workers  # type: ignore[attr-defined]

    # ---------- 动画线程函数 ----------
    def spining(event: Event, lock: Lock) -> None:
        """
        后台线程函数：每隔 0.1 秒检查一次 event，若未结束则打印旋转光标和当前进度。

        参数：
            event: 用于通知线程退出的 Event 对象
            lock:  保护共享变量 done 的锁（虽然本函数只读取，但主线程会修改，锁保证可见性）
        """
        for c in cycle(r"\|/-"):  # 旋转字符序列
            with lock:
                # 打印进度条，\r 实现原地刷新
                print(f"运行中... ({done:4}/{len(files):4}) {c}", end="\r")
            if event.wait(0.1):  # 等待 0.1 秒，若 event 被设置则退出循环
                # 最后一次刷新，显示完成信息
                print(f"运行中... ({done:4}/{len(files):4}) 完成")
                break

    event = Event()  # 用于通知动画线程结束
    lock = Lock()  # 保护共享变量 done
    done = 0  # 已完成的任务数（主线程更新，动画线程只读）
    spin = Thread(target=spining, args=(event, lock))

    print(f"正在使用 {real_workers} 个进程处理 {len(files)} 个文件...")
    t0 = perf_counter()
    spin.start()  # 启动动画线程

    with executor:
        futures = []
        # 提交所有任务到进程池
        for f in files:
            future = executor.submit(rename_and_copy, f, output)
            futures.append(future)

        # 每完成一个任务，增加 done 计数（使用锁保证线程安全）
        for _ in as_completed(futures):
            with lock:
                done += 1

    # 通知动画线程结束并等待其完全退出
    event.set()
    spin.join()

    t0 = perf_counter() - t0
    print(f"处理完成 {len(files)} 个文件，耗时 {t0:9.6f} 秒。")


# ===================== 路径检查辅助函数 =====================
def _check(
    path: Path, dir: bool, exist: bool = True, strict: bool = False, create: bool = True
) -> bool:
    """
    检查路径是否存在、类型是否符合预期（文件/目录），并可选地自动创建缺失的路径。

    参数：
        path:   要检查的路径（Path 对象）
        dir:    若为 True，期望路径是目录；若为 False，期望路径是文件
        exist:  若为 True，期望路径存在；若为 False，期望路径不存在（本程序中未使用 False 情况）
        strict: 若为 True，检查失败时直接抛出异常；若为 False，返回布尔值
        create: 当路径不存在且 strict=False 时，是否自动创建（目录则创建目录，文件则创建空文件）

    返回值：
        检查通过时返回 True，失败时（且 strict=False）返回 False。

    异常：
        当 strict=True 时可能抛出 FileNotFoundError 或 FileExistsError。
    """
    if exist:
        if not path.exists():
            if strict:
                raise FileNotFoundError(f"{str(path)} 不存在")
            if create:
                if dir:
                    path.mkdir(parents=True)  # 创建目录（包括父目录）
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)  # 确保父目录存在
                    path.touch()  # 创建空文件
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
    """构建并返回命令行参数解析器（argparse.ArgumentParser）的解析结果。"""
    ap = ArgumentParser(
        prog="Phigros官谱分析器",
        description="一个计算谱面文件音符数量和 BPM，并自动复制后重命名的命令行工具",
    )
    ap.add_argument("source_folder", help="原谱面文件存放文件夹")
    ap.add_argument("save_folder", help="处理后谱面文件的存放文件夹")
    ap.add_argument(
        "process_number",
        nargs="?",
        help="程序使用的进程数目（留空使用 CPU 核心数目）",
        type=int,
        default=None,
    )
    return ap.parse_args()


# ===================== 命令行入口 =====================
def main():
    """程序入口：解析命令行参数，检查路径合法性，调用 run() 执行核心处理。"""
    args = _arg_parser()
    src = Path(args.source_folder)
    out = Path(args.save_folder)
    _check(src, True, strict=True)  # 源目录必须存在且为目录
    _check(out, True, create=True)  # 目标目录若不存在则自动创建

    run(src, out, args.process_number)


if __name__ == "__main__":
    main()
