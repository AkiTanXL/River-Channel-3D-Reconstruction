# RC3DR - Agent Guidelines

## Project Overview
RC3DR (River Channel 3D Reconstruction) is a Python-based GIS application for 3D river channel reconstruction using measured bank points, cross-sections, and interpolation techniques. The project uses PyQt5 for GUI, GeoPandas for spatial data processing, and various interpolation algorithms.

## Build and Development Commands

### Environment Setup
```bash
# Install dependencies (typical packages used - check actual requirements)
pip install geopandas shapely pyqt5 matplotlib numpy pandas scipy
```

### Running the Application
```bash
# From src directory
cd src
python GUI.py
```

### Testing
This project doesn't have a formal test suite. To test individual modules:
```bash
# Test module0_data_preprocessing
python -c "import module0_data_preprocessing; print('Module loaded successfully')"

# Test module1_thalweg_interpolation
python -c "import module1_thalweg_interpolation; print('Module loaded successfully')"

# Test all modules
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
print('All modules loaded successfully')
"
```

### Linting and Code Quality
```bash
# Basic Python syntax check
python -m py_compile src/*.py

# Type checking (if types are used)
python -m mypy src/ --ignore-missing-imports

# Code formatting (if not using black/isort)
python -m autopep8 --in-place --aggressive --aggressive src/*.py
```

## Code Style Guidelines

### Imports
- Group imports in this order:
  1. Standard library imports
  2. Third-party imports
  3. Local application imports
- Use absolute imports for local modules
- Keep imports at the top of the file

```python
# Good example from config.py:1-10
"""
RC3DR 项目配置
"""

import os
import json
from typing import Dict, Any, Optional

# Third-party imports go here if any

# Local imports
# from . import other_module
```

### Formatting
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 120 characters
- Use double quotes for docstrings and single quotes for strings
- Add spaces around operators and after commas

```python
# Good example from utils.py:20-21
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', str(s))]
```

### Types
- Use type hints for function parameters and return values
- Import typing annotations at the top
- Use Optional for parameters that can be None

```python
# Good example from config.py:72-77
def load_from_file(self, config_file: str):
    """
    从配置文件加载配置

    Args:
        config_file: 配置文件路径（支持JSON格式）
    """
```

### Naming Conventions
- **Classes**: PascalCase (e.g., `RC3DRConfig`, `RC3DRLogger`)
- **Functions/Methods**: snake_case (e.g., `load_from_file`, `get_module_logger`)
- **Variables**: snake_case (e.g., `config_file`, `log_dir`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `DEFAULT_CONFIG`)
- **Private methods**: start with underscore (e.g., `_deep_update`, `_init_config`)

### Error Handling
- Use try-except blocks for file operations and external dependencies
- Log exceptions using the project's logger system
- Provide meaningful error messages in Chinese (as this is a Chinese project)

```python
# Good example from config.py:88-91
try:
    with open(config_file, 'r', encoding='utf-8') as f:
        file_config = json.load(f)
    # 深度合并配置
    self._deep_update(self.config, file_config)
    return True
except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
    # 如果文件不存在或格式错误，使用默认配置
    print(f"警告：无法加载配置文件 {config_file}，使用默认配置。错误：{e}")
    return False
```

### Documentation
- Write docstrings in Chinese (project requirement)
- Use triple quotes for docstrings
- Include Args, Returns, and Raises sections
- Document the purpose and usage of each function

```python
# Good example from config.py:131-140
def get(self, key: str, default: Any = None) -> Any:
    """
    获取配置值

    Args:
        key: 配置键，支持点号分隔，如 'logging.level'
        default: 默认值（如果键不存在）

    Returns:
        配置值
    """
```

### Logging
- Use the project's logger system (`logger.py`)
- Get module-specific loggers using `get_module_logger('module_name')`
- Log at appropriate levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Include context in log messages

```python
# Good example from module imports
try:
    from logger import get_module_logger
    logger = get_module_logger('utils')
except ImportError:
    logger = logging.getLogger('rc3dr.utils')
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
```

## Project Structure

```
RC3DR/
├── src/                    # Source code
│   ├── config.py          # Configuration management
│   ├── logger.py          # Logging system
│   ├── utils.py           # Utility functions
│   ├── GUI.py             # Main GUI application
│   ├── module0_data_preprocessing.py
│   ├── module1_thalweg_interpolation.py
│   ├── module2_bank_interpolation.py
│   ├── module3_profile_interpolation.py
│   ├── module4_dem_generate.py
│   └── module5_validation_correction.py
├── data/                  # Data directories
│   ├── raw_data/         # Input shapefiles
│   ├── intermediate_data/ # Processed intermediate files
│   └── result/           # Final outputs (DEM, TIN)
├── design_document/      # Module design documents (Chinese)
├── logs/                 # Application logs
└── AGENTS.md            # This file
```

## Module Architecture

1. **Module 0**: Data preprocessing - reads raw shapefiles, identifies river banks
2. **Module 1**: Thalweg interpolation - interpolates along the river centerline
3. **Module 2**: Bank interpolation - interpolates along river banks
4. **Module 3**: Profile interpolation - handles cross-section interpolation
5. **Module 4**: DEM generation - creates Digital Elevation Model
6. **Module 5**: Validation and correction - quality control

## Data Flow
- Input: Shapefiles in `data/raw_data/`
- Processing: Intermediate files in `data/intermediate_data/`
- Output: DEM and TIN in `data/result/`

## Important Notes for Agents

1. **Language**: This is a Chinese project. Docstrings and UI elements are in Chinese.
2. **GIS Data**: The project processes shapefiles using GeoPandas and Shapely.
3. **Threading**: GUI uses QThread for background processing to prevent UI freezing.
4. **Configuration**: Use the `config.py` singleton for configuration management.
5. **Logging**: Always use the project's logger system, not print statements.
6. **Paths**: Use relative paths from the project root, resolved via `config.resolve_path()`.
7. **Error Handling**: Catch and log exceptions appropriately, don't crash silently.
8. **Performance**: Some operations process large spatial datasets - optimize for memory usage.
9. **Dependencies**: The project relies on PyQt5, GeoPandas, NumPy, SciPy, Matplotlib.
10. **Testing**: No formal test suite exists - test manually by running modules.

## Common Pitfalls to Avoid

1. **Absolute paths**: Don't hardcode absolute paths, use the configuration system.
2. **Memory leaks**: Large GeoDataFrames can consume memory - release when done.
3. **UI blocking**: Always run heavy computations in worker threads.
4. **File encoding**: Use UTF-8 for all file operations.
5. **Shapefile dependencies**: Remember shapefiles consist of multiple files (.shp, .shx, .dbf, .prj).
6. **Coordinate systems**: Ensure consistent CRS when processing spatial data.
7. **Interpolation methods**: The project uses cubic spline and PCHIP interpolation.
8. **Logging levels**: Use appropriate log levels (INFO for progress, ERROR for failures).

## When Adding New Features

1. Follow the existing module pattern (see `module0_data_preprocessing.py`)
2. Add design document in `design_document/` (in Chinese)
3. Update configuration if new settings are needed
4. Add appropriate logging throughout
5. Test with sample data in `data/raw_data/`
6. Ensure backward compatibility with existing modules
7. Document the feature in Chinese

## Code Review Checklist

- [ ] Follows naming conventions
- [ ] Includes type hints
- [ ] Has Chinese docstrings
- [ ] Uses project logger
- [ ] Handles errors appropriately
- [ ] Follows import ordering
- [ ] No hardcoded paths
- [ ] Thread-safe for GUI operations
- [ ] Memory efficient for large datasets
- [ ] Compatible with existing modules