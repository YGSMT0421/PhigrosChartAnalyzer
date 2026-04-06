"""
测试程序，用于检测count_notes.py是否可以正确判断谱面文件
"""

import sys
from pathlib import Path

# 把项目根目录加进 Python 路径
sys.path.append(str(Path(__file__).resolve().parent.parent))

from count_notes import rename, CountErrorCode


CHART_DIR = Path(__file__).parent / "charts"


def test_valid_ez_chart() -> None:
    name = rename(str(CHART_DIR / "valid_EZ_chart.json"))
    assert name == "Chart_EZ_3_114.514.json"


def test_valid_ez_chart_no_suffix() -> None:
    name = rename(str(CHART_DIR / "valid_EZ_chart_no_suffix"))
    assert name == "Chart_EZ_3_114.514.json"


def test_valid_ez_chart_no_difficulty() -> None:
    name = rename(str(CHART_DIR / "valid_chart_no_difficulty.json"))
    assert name == "Chart_Unknown_3_1919.81.json"


def test_invalid_chart_gbk_extra_chars() -> None:
    name = rename(str(CHART_DIR / "invalid_EZ_chart_gbk_extra_char.json"))
    assert name == CountErrorCode.UnicodeDecodeError


def test_invalid_chart_no_such_file() -> None:
    name = rename(str(CHART_DIR / "no_such_file.json"))
    assert name == CountErrorCode.FileNotFoundError


def test_invalid_chart_not_a_valid_json_file() -> None:
    name = rename(str(CHART_DIR / "invalid_not_a_chart.json"))
    assert name == CountErrorCode.JsonDecodeError


def test_invalid_chart_field_not_exist() -> None:
    name = rename(str(CHART_DIR / "invalid_EZ_chart_no_notesBelow.json"))
    assert name == CountErrorCode.FieldNotExistError
