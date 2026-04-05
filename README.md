# 📊 Phigros Chart Analyzer

<p align="center">
  <a href="https://github.com/YGSMT0421/PhigrosChartAnalyzer/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/YGSMT0421/PhigrosChartAnalyzer/ci.yml?style=flat-square&logo=github" alt="GitHub Actions">
  </a>
  <a href="https://github.com/YGSMT0421/PhigrosChartAnalyzer/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/YGSMT0421/PhigrosChartAnalyzer?style=flat-square" alt="License">
  </a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square" alt="Platform">
</p>

## ⚠️ 注意
> [!IMPORTANT]
> 本文档由AI生成，不保证正确性

## 📋 项目简介

**Phigros官谱分析器**是一个专为《Phigros》音乐游戏谱面文件设计的批量处理工具。该工具能够自动解析官方谱面JSON文件，提取谱面关键数据（难度、音符数量、BPM），并将这些信息整合到新的文件名中，实现谱面文件的智能整理与规范化管理。

> 🎯 **核心功能**：自动识别谱面难度、统计音符总数、提取BPM值，并将这些信息整合为标准化文件名格式

## ✨ 主要特性

- 🔍 **自动分析**：批量解析Phigros谱面JSON文件
- 📈 **数据统计**：精确计算每个谱面的音符总数和BPM
- 🏷️ **智能识别**：基于文件名自动识别谱面难度（EZ/HD/IN/AT/Legacy）
- 📁 **智能重命名**：将难度、Note数和BPM作为新的文件名，格式统一规范
- ⚡ **高效处理**：多进程并行处理，充分利用CPU性能
- 🎨 **实时进度**：命令行进度动画显示处理状态
- 🔧 **错误处理**：完善的错误检测和报告机制

## 🚀 快速开始

### 环境要求
- **Python 3.10** 或更高版本
- 仅使用Python标准库，无需额外安装依赖

### 安装方式

```bash
# 克隆仓库
git clone https://github.com/YGSMT0421/PhigrosChartAnalyzer.git
cd PhigrosChartAnalyzer

# （可选）创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows
```

### 基本使用

```bash
python count_notes.py <源文件夹路径> <目标文件夹路径>
```

### 使用示例

```bash
# 示例1：基本使用（自动使用CPU核心数处理）
python count_notes.py ./raw_charts ./processed_charts

# 示例2：指定4个处理进程
python count_notes.py ./raw_charts ./processed_charts 4

# 示例3：处理当前目录下的谱面
python count_notes.py ./input ./output
```

## 📂 文件结构示例

### 处理前
```
raw_charts/
├── MyChart_HD.json          # 会被识别为HD难度
├── AnotherChart_IN.json     # 会被识别为IN难度
├── EasyChart_EZ.json        # 会被识别为EZ难度
└── Legacy_Version.json      # 会被识别为Legacy难度
```

### 处理后
```
processed_charts/
├── Chart_HD_1280_180.0.json      # 格式：Chart_难度_音符数_BPM.json
├── Chart_IN_920_145.5.json       # HD难度，1280个音符，BPM 180.0
├── Chart_EZ_320_120.0.json       # IN难度，920个音符，BPM 145.5
└── Chart_Legacy_750_160.0.json   # EZ难度，320个音符，BPM 120.0
```

## 📖 详细使用说明

### 命令行参数

| 参数 | 必需 | 类型 | 描述 | 默认值 |
|------|------|------|------|--------|
| `source-folder` | 是 | 路径 | 包含原始谱面文件的目录路径 | - |
| `save-folder` | 是 | 路径 | 处理后文件的输出目录 | - |
| `process-number` | 否 | 整数 | 使用的进程数（留空使用CPU核心数） | CPU核心数 |

### 文件名重命名规则

程序按照以下格式生成新的文件名：

```
Chart_[难度]_[音符总数]_[BPM].json
```

**字段说明：**
- `难度`：自动识别的谱面难度等级
- `音符总数`：所有判定线上`notesAbove`和`notesBelow`的总和
- `BPM`：第一条判定线的BPM值（浮点数）

### 难度识别规则

程序按**优先级顺序**识别谱面难度：

| 文件名关键词 | 识别难度 | 输出示例 |
|-------------|----------|----------|
| `EZ` | EZ难度 | `Chart_EZ_xxx_xxx.json` |
| `HD` | HD难度 | `Chart_HD_xxx_xxx.json` |
| `IN` | IN难度 | `Chart_IN_xxx_xxx.json` |
| `AT` | AT难度 | `Chart_AT_xxx_xxx.json` |
| `Legacy` | Legacy难度 | `Chart_Legacy_xxx_xxx.json` |
| （无匹配） | Unknown | `Chart_Unknown_xxx_xxx.json` |

> ⚠️ **特殊标记**：如果文件名包含"Error"，会在难度后添加`_Error`标记（如`Chart_HD_Error_xxx_xxx.json`）

## 🔧 技术实现

### 核心算法

```python
# 音符总数计算逻辑
notes = sum(
    len(line['notesAbove']) + len(line['notesBelow'])
    for line in data['judgeLineList']
)

# BPM提取逻辑
bpm = data['judgeLineList'][0]['bpm']
```

### 并行处理架构

- 使用`ProcessPoolExecutor`实现多进程并行
- 主线程负责进度监控和动画显示
- 每个谱面文件独立处理，无数据竞争问题
- 自动根据CPU核心数优化进程数量

### 错误处理机制

程序检测以下错误情况并提供清晰反馈：

1. **JSON解析错误** - 文件格式无效
2. **文件不存在** - 源文件丢失
3. **权限错误** - 读写权限不足  
4. **编码错误** - UTF-8解码失败
5. **字段缺失** - 非标准谱面文件

## 📝 常见问题解答

### Q: 程序支持递归处理子目录吗？
**A:** 目前版本仅处理指定目录下的文件，不递归处理子目录。

### Q: 处理过程中可以中断吗？
**A:** 可以按`Ctrl+C`中断程序，已处理的文件会保留在目标目录。

### Q: 如何批量处理不同文件夹的谱面？
**A:** 可以将所有谱面文件集中到一个文件夹，或多次运行程序。

### Q: 程序会修改原始文件吗？
**A:** 不会。程序只读取原始文件，并将处理后的副本保存到目标文件夹。

### Q: 支持自定义命名规则吗？
**A:** 目前使用固定命名规则，可通过修改源码`rename()`函数调整。

## 🤝 贡献指南

欢迎为项目贡献代码或提出建议！

1. **Fork** 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 **Pull Request**

### 开发要求
- 遵循现有代码风格（类型注解、文档字符串）
- 确保新增功能有相应的测试
- 更新相关文档（包括本README）

## 📄 许可证

本项目基于 **MIT License** 开源。详见 [LICENSE](LICENSE) 文件。

## 📞 联系与支持

- **项目主页**：[https://github.com/YGSMT0421/PhigrosChartAnalyzer](https://github.com/YGSMT0421/PhigrosChartAnalyzer)
- **问题反馈**：[GitHub Issues](https://github.com/YGSMT0421/PhigrosChartAnalyzer/issues)

---

<p align="center">
  <sub>为 Phigros 社区打造的实用工具 ✨</sub><br>
  <sub>如果这个项目对你有帮助，请给个 ⭐ 支持一下哦！</sub>
</p>

---

*本文档由AI辅助生成，内容仅供参考，如有疑问请查看源代码或提交Issue。*
