# RC3DR - 河道三维重建系统

**RC3DR (River Channel 3D Reconstruction)** 是一个基于Python的GIS应用程序，用于使用实测河岸点、横剖面和插值技术进行河道三维重建。项目采用PyQt5构建GUI界面，使用GeoPandas进行空间数据处理，实现多种插值算法。

![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows%7CLinux%7CMacOS-lightgrey)

**联系人**: xl_tan_xyz@163.com

## 项目概述

RC3DR旨在为水利工程、环境科学和GIS领域提供专业的河道三维重建解决方案。系统通过处理实测河岸点、河岸线、横剖面点等空间数据，自动进行河道三维点云重建，为后续DEM生成提供高质量数据基础。

### 主要特性

- 🚀 **全自动处理流程**：从原始数据到三维点云生成的完整自动化流程
- 🗺️ **智能空间分析**：自动识别左右河岸、推算流向、拓扑闭合
- 📊 **多种插值算法**：支持三次样条插值、线性插值、PCHIP插值
- 🖥️ **现代化GUI界面**：基于PyQt5的图形用户界面，操作直观
- 📈 **高质量中间结果**：生成Shapefile格式的详细中间处理结果
- 🔧 **模块化架构**：核心功能模块化，支持独立测试和扩展

## 系统架构

### 模块化设计

RC3DR采用模块化设计，核心处理流程包含四个主要模块：

```
┌─────────────────────────────────────────────────────────────┐
│                     RC3DR 系统架构                          │
├─────────────────────────────────────────────────────────────┤
│ 模块0: 数据预处理 → 模块1: 深泓线插值 → 模块2: 河岸插值      │
│                                                            │
│                    → 模块3: 剖面插值 →                     │
└─────────────────────────────────────────────────────────────┘
```

### 数据流程

```
原始Shapefile数据 → 预处理 → 中间结果 → 插值计算 → DEM生成 → 最终输出
```

## 快速开始

### 环境要求

- Python 3.8+
- 推荐使用Anaconda或Miniconda管理环境

### 安装依赖

```bash
# 安装核心依赖
pip install geopandas shapely pyqt5 matplotlib numpy pandas scipy
```

### 运行应用程序

```bash
# 进入项目目录
cd RC3DR

# 方式1：使用便捷脚本（推荐）
start_gui.bat      # Windows
./start_gui.sh     # Linux/Mac

# 方式2：直接运行
python gui/main.py
```

## 项目结构

```
RC3DR/
├── gui/                    # GUI目录（重构后的模块化界面）
│   ├── main.py            # 应用启动入口
│   ├── base.py            # BaseModuleUI基础类
│   ├── main_window.py     # MainWindow主窗口
│   ├── components/         # 可复用UI组件
│   │   ├── log_handler.py # 日志处理
│   │   └── worker.py      # 异步工作线程
│   └── modules/           # 各模块UI
│       ├── module0_ui.py  # 模块0：数据预处理
│       ├── module1_ui.py  # 模块1：深泓线插值
│       ├── module2_ui.py  # 模块2：河岸插值
│       └── module3_ui.py  # 模块3：剖面插值
├── src/                    # 后端处理模块
│   ├── config.py          # 配置管理（单例模式）
│   ├── logger.py          # 日志系统
│   ├── utils.py           # 通用工具函数
│   ├── module0_data_preprocessing.py      # 模块0：数据预处理
│   ├── module1_thalweg_interpolation.py   # 模块1：深泓线插值
│   ├── module2_bank_interpolation.py      # 模块2：河岸插值
│   ├── module3_profile_interpolation.py   # 模块3：剖面插值
│   ├── module4_dem_generate.py            # 模块4：DEM生成（框架）
│   └── module5_validation_correction.py   # 模块5：验证与校正（框架）
├── data/                  # 数据目录
│   ├── raw_data/         # 原始输入数据（Shapefile格式）
│   ├── intermediate_data/ # 中间处理结果
│   └── result/           # 最终输出结果（DEM）
├── design_document/      # 模块设计文档（中文）
├── logs/                 # 应用程序日志
├── gui_config.json       # GUI路径配置文件
├── start_gui.bat         # Windows启动脚本
├── start_gui.sh          # Linux/Mac启动脚本
└── AGENTS.md            # 开发人员指南
```

## 详细功能模块

### 模块0：数据预处理 (`module0_data_preprocessing.py`)

**功能**：读取原始Shapefile数据，进行河岸识别、点分类、排序和标准化处理。

**输入数据**：
- `data/raw_data/河岸线.shp` - 原始河岸线（两条折线）
- `data/raw_data/实测河岸点.shp` - 实测河岸点（包含x, y, z坐标的字段）
- `data/raw_data/剖面点.shp` - 实测剖面点

**输出数据**：
- `data/intermediate_data/河岸线.shp` - 识别后的河岸线（左岸id=0，右岸id=1）
- `data/intermediate_data/河道边界.shp` - 河道边界多边形
- `data/intermediate_data/左河岸点.shp` - 排序后的左河岸点
- `data/intermediate_data/右河岸点.shp` - 排序后的右河岸点
- `data/intermediate_data/剖面点.shp` - 标准化编码的剖面点

**核心算法**：
1. **剖面质心拟合与流向推算**：根据实测剖面点计算河流整体流向
2. **左右河岸智能拓扑判别**：基于流向向量自动识别左右河岸
3. **曲线投影寻址与排序**：将河岸点投影到岸线上按里程排序
4. **河道面拓扑闭合与方向一致性校验**：确保生成的河道多边形拓扑正确

### 模块1：深泓线插值 (`module1_thalweg_interpolation.py`)

**功能**：沿河道中心线进行高程插值，生成深泓线高程数据。

**输入数据**：
- `data/intermediate_data/河岸线.shp`
- `data/intermediate_data/剖面点.shp`

**输出数据**：
- `data/intermediate_data/河道轴线.shp` - 平滑河道轴线
- `data/intermediate_data/深泓点.shp` - 各剖面最低点
- `data/intermediate_data/深泓线.shp` - 拟合的深泓线
- `data/intermediate_data/深泓点内插.shp` - 内插的深泓点（包含x, y, z）

**用户指定参数**：
- **步长**：深泓线上平面内插的等距步长（默认5.0米）

**核心算法**：
1. **高精度河道轴线提取**：采用"等距引导点 + 严格中线捕捉 + 滑动平均滤波"复合算法
2. **基于Pchip保形插值的防过冲算法**：使用PchipInterpolator防止深泓线在弯道处过冲
3. **向心衰减包络线机制**：强制深泓线在空白区域贴合河道几何中心
4. **空间拓扑投影与高程三次样条插值**：将弯曲河道一维化进行高程插值

### 模块2：河岸插值 (`module2_bank_interpolation.py`)

**功能**：沿河岸线进行高程插值，生成连续的河岸高程数据。

**输入数据**：
- `data/intermediate_data/河岸线.shp`
- `data/intermediate_data/深泓线.shp`
- `data/intermediate_data/深泓点内插.shp`
- `data/intermediate_data/左河岸点.shp`
- `data/intermediate_data/右河岸点.shp`

**输出数据**：
- `data/intermediate_data/左河岸点内插.shp` - 内插的左河岸点
- `data/intermediate_data/右河岸点内插.shp` - 内插的右河岸点
- `data/intermediate_data/深泓点内插.shp` - 更新后的深泓点内插数据

**用户指定参数**：
- **距离阈值**：虚拟横断面与河岸线交点的最大有效距离（默认300.0米）

**核心算法**：
1. **曲线切向量与法向量解析算法**：计算深泓线上各点的精确法向量
2. **空间超长射线求交与最近邻过滤算法**：求取虚拟横断面与河岸线的交点
3. **高性能向量化遍历机制**：使用itertuples优化循环性能

### 模块3：剖面插值 (`module3_profile_interpolation.py`)

**功能**：处理横剖面数据，进行剖面内和剖面间的高程插值。

**输入数据**：
- `data/intermediate_data/深泓点内插.shp`
- `data/intermediate_data/左河岸点内插.shp`
- `data/intermediate_data/右河岸点内插.shp`
- `data/intermediate_data/剖面点.shp`

**输出数据**：
- `data/intermediate_data/剖面点内插.shp` - 高密度三维点云

**用户指定参数**：
- **横向步长**：横断面上平面点的致密化步长（默认2.0米）

**核心算法**：
1. **高保真河床形态建模**：将实测剖面降维归一化为形态函数
2. **自适应空间形态平滑过渡算法**：基于纵向距离比例混合上下游剖面形态
3. **动态高程基准面校正算法**：通过深泓线高程校准相对形态
4. **矩阵向量化加速技术**：使用NumPy张量运算替代标量循环

### 模块4和模块5

项目包含模块4（DEM生成）和模块5（验证与校正）的框架，用于后续扩展完整的DEM生成和验证功能。

## 数据格式要求

### 输入数据准备

1. **河岸线** (`河岸线.shp`)
   - 格式：Polyline Shapefile
   - 要求：包含两条折线，分别代表左右河岸
   - 坐标系：建议使用投影坐标系
   - 相关文件：确保.shx, .dbf, .prj文件存在

2. **实测河岸点** (`实测河岸点.shp`)
   - 格式：Point Shapefile
   - 属性字段：必须包含x, y, z坐标信息字段（字段名在GUI中指定）
   - 坐标系：与河岸线一致

3. **剖面点** (`剖面点.shp`)
   - 格式：Point Shapefile
   - 属性字段：必须包含剖面编号和点编号信息
   - 编码格式：支持原始编码如"P001_01"或"剖面1_点1"

### 输出数据说明

1. **中间结果** (`data/intermediate_data/`)
   - 各模块输出的Shapefile格式中间文件
   - 用于调试和质量检查

2. **最终结果** (`data/result/`)
   - 用于存储最终输出的DEM文件（当模块4实现后）

## 使用指南

### 1. 准备数据

将原始数据文件放置在 `data/raw_data/` 目录下：
- `河岸线.shp` (及相关文件 .shx, .dbf, .prj)
- `实测河岸点.shp` (及相关文件)
- `剖面点.shp` (及相关文件)

### 2. 运行应用程序

```bash
cd src
python GUI.py
```

### 3. 界面操作

1. **选择工作目录**：指定项目根目录（包含src/和data/的目录）
2. **输入参数配置**：
   - 实测河岸点的高程字段名（如"z"或"elevation"）
   - 深泓线插值步长（默认2.0米）
   - 河岸交点距离阈值（默认500.0米）
   - 剖面横向插值步长（默认2.0米）
3. **运行处理**：点击"开始处理"按钮
4. **查看进度**：通过进度条和日志窗口监控处理状态
5. **查看结果**：处理完成后在`data/result/`目录查看DEM文件

## 开发指南

### 代码风格

项目遵循PEP 8规范，具体要求见 `AGENTS.md` 文件。

### 测试

```bash
# 测试单个模块
python -c "import module0_data_preprocessing; print('模块0加载成功')"

# 测试所有模块
python -c "
import module0_data_preprocessing
import module1_thalweg_interpolation
import module2_bank_interpolation
import module3_profile_interpolation
import module4_dem_generate
import module5_validation_correction
import config
import logger
import utils
print('所有模块加载成功')
"
```

### 代码质量检查

```bash
# 语法检查
python -m py_compile src/*.py

# 类型检查
python -m mypy src/ --ignore-missing-imports

# 代码格式化
python -m autopep8 --in-place --aggressive --aggressive src/*.py
```

## 故障排除

### 常见问题

1. **导入错误：找不到geopandas**
   ```bash
   pip install geopandas
   ```

2. **Shapefile读取失败**
   - 确保所有相关文件存在（.shp, .shx, .dbf, .prj）
   - 检查文件路径和权限
   - 验证坐标系一致性

3. **内存不足**
   - 减少处理数据量
   - 增加系统内存
   - 优化数据处理流程

4. **GUI界面无响应**
   - 确保处理在后台线程中进行
   - 检查日志文件了解处理状态
   - 减少同时处理的数据量

### 日志文件

系统日志存储在 `logs/` 目录下，文件名为 `rc3dr_YYYYMMDD.log`。遇到问题时，首先检查日志文件获取详细信息。

## 性能优化

### 内存管理

- 大型GeoDataFrame处理完成后及时释放
- 使用分块处理大规模数据
- 避免不必要的数据复制

### 计算优化

- 使用向量化操作替代循环
- 合理使用缓存机制
- 选择适当的插值算法

## 许可证

本项目采用 MIT 许可证。

## 贡献指南

如有问题或建议，请联系：xl_tan_xyz@163.com

---

**RC3DR** - 让河道三维重建更简单、更精确！

