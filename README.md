<div align="center">

<img src="https://raw.githubusercontent.com/ImJingLan/duplicate-File-Tools/refs/heads/main/assets/logo.png" width="290" alt="DedupTool Banner">

# 🔍 Duplicate File Manager

**智能文件去重管理工具**

一个集文件扫描、重复检测、智能去重和规则管理于一体的现代化桌面应用

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Tests](https://img.shields.io/badge/Tests-122%20passed-success?style=flat-square&logo=pytest)](./tests)
[![License](https://img.shields.io/badge/License-MPL%202.0-blue?style=flat-square)](./LICENSE)
[![Conventional Commits](https://img.shields.io/badge/Commits-Conventional-fe5196?style=flat-square&logo=conventionalcommits)](https://conventionalcommits.org)

</div>

---

## 📋 目录

- [功能特性](#-功能特性)
- [项目结构](#-项目结构)
- [快速开始](#-快速开始)
- [使用指南](#-使用指南)
- [配置说明](#-配置说明)
- [测试](#-测试)
- [CI/CD](#-cicd)
- [技术栈](#-技术栈)

---

## ✨ 功能特性

### 🔎 文件扫描引擎
- **递归目录遍历** — 深度优先扫描，自动跳过不可访问路径
- **元数据提取** — 记录文件大小、修改时间、完整路径
- **灵活过滤** — 支持最小文件大小过滤、glob 模式排除
- **实时进度** — 回调机制支持 UI 进度条实时更新

### 🧬 重复检测算法
- **三级筛选策略** — 文件大小 → 哈希值 → 重复确认
- **双哈希支持** — MD5（快速）与 SHA-256（安全）可选
- **并行计算** — 线程池加速大文件批量哈希
- **精确结果** — 哈希值 + 文件属性双重确认

### 🛡️ 智能去重引擎

| 模式 | 说明 |
|------|------|
| 🏆 **智能评分**（推荐） | 多维度路径评分，自动保留最优副本 |
| 📦 **保留最大文件** | 优先保留磁盘占用最大的版本 |
| ⏱️ **保留最新文件** | 基于修改时间保留最新版本 |
| 🎯 **路径规则匹配** | 自定义正则表达式匹配保留规则 |

### 🔒 保护规则系统
- **50+ 预设规则** — 覆盖游戏文件、开发依赖、系统组件
- **可视化编辑器** — 浏览器端 CRUD 管理界面
- **正则表达式** — 支持标准正则，实时校验
- **路径测试** — 输入样例路径即时验证匹配效果

### 📝 脚本生成与执行
- **双平台支持** — 生成 Windows `.bat` 和 Linux `.sh` 脚本
- **MD5 安全校验** — 执行前二次确认文件内容一致
- **暂存区机制** — 文件先移动而非直接删除，安全可回滚
- **操作预览** — 支持 dry-run 预览模式

### 🎨 现代化 Web 界面
- **单页应用** — 5 个标签页，流畅切换无刷新
- **实时监控** — 扫描进度、任务状态实时轮询
- **历史管理** — 任务记录查询、CSV/JSON 导出、操作回滚
- **响应式设计** — 适配桌面、平板和移动端

---

## 📁 项目结构

```
GUI_Version/
├── run.py                          # 应用启动入口
├── requirements.txt                # Python 依赖
│
├── config/
│   └── settings.py                 # 全局配置（日志、路径、偏好）
│
├── core/
│   ├── scanner.py                  # 文件扫描模块
│   ├── detector.py                 # 重复检测模块（并行哈希）
│   ├── pattern_manager.py          # 保护规则 CRUD 管理器
│   ├── dedup_engine.py             # 智能去重决策引擎
│   └── script_generator.py         # 脚本生成器（.bat / .sh）
│
├── web/
│   ├── app.py                      # Flask 应用工厂
│   ├── routes/
│   │   ├── scan_routes.py          # 扫描任务 API
│   │   ├── dedup_routes.py         # 去重操作 API
│   │   ├── pattern_routes.py       # 规则管理 API
│   │   └── history_routes.py       # 历史记录 API
│   ├── templates/index.html        # SPA 主页面
│   └── static/
│       ├── css/style.css           # 样式系统
│       └── js/main.js              # 前端逻辑（纯原生 JS）
│
├── data/
│   └── patterns.json               # 50 条预设保护规则
│
├── tests/
│   ├── test_scanner.py             # 扫描模块测试 (13)
│   ├── test_detector.py            # 检测模块测试 (16)
│   ├── test_pattern_manager.py     # 规则管理测试 (32)
│   ├── test_dedup_engine.py        # 去重引擎测试 (24)
│   ├── test_script_generator.py    # 脚本生成测试 (31)
│   └── test_integration.py         # 端到端集成测试 (6)
│
├── tools/
│   ├── generate_changelog.py       # 变更日志生成器
│   └── weekly_snapshot.py          # 周快照版本号生成器
│
├── .github/
│   └── workflows/
│       ├── release.yml             # 发布工作流
│       └── weekly-snapshot.yml     # 每周快照工作流
│
├── .gitignore
├── LICENSE                         # MPL 2.0
└── README.md
```

---

## 🚀 快速开始

### 环境要求

- **Python** ≥ 3.12
- **pip** 最新版本

### 安装

```bash
# 克隆仓库
git clone <your-repo-url>
cd GUI_Version

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 启动应用

```bash
python run.py
```

浏览器访问 **http://127.0.0.1:5000**

### 运行测试

```bash
python -m pytest tests/ -v
```

```
============================= test session starts ==============================
collected 122 items

tests/test_scanner.py .............                                       [ 10%]
tests/test_detector.py ................                                   [ 23%]
tests/test_pattern_manager.py ................................            [ 50%]
tests/test_dedup_engine.py ........................                       [ 69%]
tests/test_script_generator.py ...............................            [ 95%]
tests/test_integration.py ......                                          [100%]

============================= 122 passed in 0.77s ==============================
```

---

## 📖 使用指南

### 1️⃣ 扫描文件

1. 打开 **扫描任务** 标签页
2. 输入要扫描的目录路径（或点击浏览选择）
3. 配置最小文件大小和排除模式（可选）
4. 选择哈希算法（MD5 / SHA-256）
5. 点击 **开始扫描**，实时查看进度
6. 扫描完成后，切换到 **扫描结果** 标签页查看

### 2️⃣ 查看重复文件

- **汇总卡片** — 文件总数、重复组数、重复文件数、可清理数
- **重复组表格** — 点击展开查看每个组内的文件详情
- 每个组显示文件路径、大小、修改时间
- 点击 **去重** 按钮进入下一步

### 3️⃣ 执行去重

1. 切换到 **去重操作** 标签页
2. 选择去重模式（推荐使用智能评分）
3. 设置暂存目录
4. 点击 **分析预览** 查看保留/移除/保护决策
5. 确认无误后：
   - 点击 **生成脚本** 导出 `.bat`/`.sh` 文件
   - 或点击 **直接执行** 立即去重

### 4️⃣ 管理保护规则

1. 切换到 **保护规则** 标签页
2. 查看 50 条预设保护规则
3. 使用 **添加规则** 表单新增自定义规则
4. 使用正则验证功能确保表达式正确
5. 使用 **测试匹配** 验证路径是否能匹配规则
6. 通过上移/下移调整规则优先级

---

## ⚙️ 配置说明

### 应用配置

编辑 [config/settings.py](file:///config/settings.py) 修改全局配置：

```python
# 日志配置
LOG_LEVEL = "INFO"          # DEBUG / INFO / WARNING / ERROR
LOG_TO_FILE = True          # 是否输出到文件

# 去重配置
DEFAULT_DEDUP_MODE = "keep_best"   # 默认去重模式
MAX_HISTORY_RECORDS = 1000         # 最大历史记录数

# 哈希配置
CHUNK_SIZE = 64 * 1024      # 分块读取大小（字节）
```

### 用户偏好

偏好设置自动保存在 `config/user_preferences.json`，包括：

- 常用扫描路径列表
- 默认去重模式
- 排除模式配置
- 界面语言和主题

### 保护规则

规则文件位于 [data/patterns.json](file:///data/patterns.json)，格式如下：

```json
{
  "pattern": "/node_modules/",
  "name": "Node.js 程序依赖",
  "enabled": true
}
```

支持正则表达式语法（Python `re` 模块），可通过 Web 界面编辑。

---

## 🧪 测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行指定模块测试
python -m pytest tests/test_scanner.py -v

# 生成覆盖率报告
python -m pytest tests/ --cov=core --cov=config --cov-report=html

# 仅运行集成测试
python -m pytest tests/test_integration.py -v
```

| 测试文件 | 用例数 | 覆盖模块 |
|----------|--------|----------|
| `test_scanner.py` | 13 | 文件扫描 |
| `test_detector.py` | 16 | 重复检测 |
| `test_pattern_manager.py` | 32 | 规则管理 |
| `test_dedup_engine.py` | 24 | 去重引擎 |
| `test_script_generator.py` | 31 | 脚本生成 |
| `test_integration.py` | 6 | 端到端流程 |
| **合计** | **122** | **全部通过 ✅** |

---

## 🔄 CI/CD

### 每周快照发布

`.github/workflows/weekly-snapshot.yml` — 每周一 UTC 00:00 自动生成 `YYwWWx` 格式快照版本：

```bash
# 生成下一个快照版本号
python tools/weekly_snapshot.py
# 输出: 26w22a

# 获取基础标签
python tools/weekly_snapshot.py --get-base-tag
```

### 正式发布

`.github/workflows/release.yml` — 手动触发正式发布：

```bash
# 生成变更日志
python tools/generate_changelog.py --tag v1.0.0 --base v0.9.0 --with-hash
```

所有提交遵循 [约定式提交规范](https://conventionalcommits.org/zh-hans/v1.0.0/)。

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | Flask 3.0 |
| **并发处理** | `concurrent.futures.ThreadPoolExecutor` |
| **前端** | 原生 HTML5 / CSS3 / JavaScript (ES2020+) |
| **测试** | pytest 8.0 |
| **版本控制** | Git + Conventional Commits |
| **CI/CD** | GitHub Actions + Python 工具链 |

### API 端点一览

| 模块 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 📡 扫描 | `/api/scan/start` | POST | 启动扫描任务 |
| 📡 扫描 | `/api/scan/status/<id>` | GET | 实时进度查询 |
| 📡 扫描 | `/api/scan/result/<id>` | GET | 获取扫描结果 |
| 📡 扫描 | `/api/scan/tasks` | GET | 任务列表 |
| 📡 扫描 | `/api/scan/stop/<id>` | POST | 停止任务 |
| 🧹 去重 | `/api/dedup/analyze` | POST | 分析决策 |
| 🧹 去重 | `/api/dedup/preview` | POST | 操作预览 |
| 🧹 去重 | `/api/dedup/generate-script` | POST | 生成脚本 |
| 🧹 去重 | `/api/dedup/execute` | POST | 执行去重 |
| 🧹 去重 | `/api/dedup/save-script` | POST | 保存脚本 |
| 🛡️ 规则 | `/api/patterns` | GET/POST | 规则列表/新增 |
| 🛡️ 规则 | `/api/patterns/<id>` | PUT/DELETE | 更新/删除 |
| 🛡️ 规则 | `/api/patterns/move` | POST | 排序 |
| 🛡️ 规则 | `/api/patterns/test` | POST | 路径测试 |
| 📋 历史 | `/api/history` | GET | 历史列表 |
| 📋 历史 | `/api/history/<id>` | GET/DELETE | 详情/删除 |

---

<div align="center">

### 📄 License

本项目使用 [Mozilla Public License 2.0](LICENSE) 许可证

---

*Made with ❤️ for cleaner storage*

</div>
