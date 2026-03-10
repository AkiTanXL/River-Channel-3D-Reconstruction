import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline
from shapely.geometry import Point, LineString
import re
import os
import logging

try:
    from logger import get_module_logger

    logger = get_module_logger('utils')
except ImportError:
    logger = logging.getLogger('rc3dr.utils')
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', str(s))]


def interpolate_z_along_curve(known_points_shp: str, interp_points_shp: str) -> None:
    """
    沿曲线进行高程（Z值）的三次样条插值 (空间投影法修复版)
    """
    logger.info("正在进行高程内插，读取数据...")
    known_gdf = gpd.read_file(known_points_shp)
    interp_gdf = gpd.read_file(interp_points_shp)

    if 'id' not in known_gdf.columns or 'id' not in interp_gdf.columns:
        raise ValueError("输入的数据中必须包含 'id' 字段！")

    # 1. 将密集的内插点按自身ID排序，它们在空间上能够勾勒出平滑的参考曲线
    interp_gdf['sort_key'] = interp_gdf['id'].apply(natural_sort_key)
    interp_sorted = interp_gdf.sort_values('sort_key').reset_index(drop=True)

    # 构建代表“拉直”基准的参考线
    ref_coords = [(geom.x, geom.y) for geom in interp_sorted.geometry]
    ref_line = LineString(ref_coords)

    # 2. 空间拓扑投影（核心修复）：将所有点投影到基准线上，获取它们真实的物理里程(S)
    known_gdf['s'] = known_gdf.geometry.apply(lambda geom: ref_line.project(geom))
    interp_gdf['s'] = interp_gdf.geometry.apply(lambda geom: ref_line.project(geom))

    # 3. 提取插值数据
    known_sorted = known_gdf.sort_values('s').reset_index(drop=True)

    # 防止多个已知点投影到同一位置（如都在起终点外），取平均值保证 S 严格递增
    known_grouped = known_sorted.groupby('s', as_index=False)['z'].mean()
    s_known = known_grouped['s'].values
    z_known = known_grouped['z'].values

    s_interp = interp_gdf['s'].values

    # 4. 执行三次样条插值
    logger.info("应用 CubicSpline 三次样条插值...")
    cs = CubicSpline(s_known, z_known, bc_type='natural')
    z_interp = cs(s_interp)

    # 5. 更新数据与几何
    interp_gdf['z'] = z_interp
    interp_gdf['geometry'] = interp_gdf.apply(
        lambda row: Point(row.geometry.x, row.geometry.y, row['z']), axis=1
    )

    interp_gdf = interp_gdf.drop(columns=['sort_key', 's'])
    interp_gdf.to_file(interp_points_shp, encoding='utf-8')
    logger.info("高程内插并更新完成！")