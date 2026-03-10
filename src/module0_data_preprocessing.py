import os
import re
import numpy as np
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString, Polygon
import warnings
import logging

# 导入RC3DR日志系统，提供回退机制
try:
    from logger import get_module_logger
    logger = get_module_logger('module0')
except ImportError:
    # 回退到标准logging
    logger = logging.getLogger('rc3dr.module0')
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def preprocess_data(
    input_shoreline: str,
    input_bank_points: str,
    input_profile_points: str,
    output_shoreline: str,
    output_left_bank_points: str,
    output_right_bank_points: str,
    output_profile_points: str,
    output_channel_polygon: str,
    bank_x_field: str,
    bank_y_field: str,
    bank_z_field: str,
    profile_x_field: str,
    profile_y_field: str,
    profile_z_field: str,
    profile_id_field: str   # 原始剖面点ID字段，应包含数字（如 "NTH035"），用于提取剖面编号
):
    """
    数据预处理模块（Module 0）

    参数
    ----------
    input_shoreline : str
        原始河岸线 shapefile 路径（应包含两条折线）
    input_bank_points : str
        实测河岸点 shapefile 路径
    input_profile_points : str
        剖面点 shapefile 路径
    output_shoreline : str
        输出河岸线 shapefile 路径
    output_left_bank_points : str
        输出左岸河岸点 shapefile 路径
    output_right_bank_points : str
        输出右岸河岸点 shapefile 路径
    output_profile_points : str
        输出剖面点 shapefile 路径
    bank_x_field : str
        实测河岸点中存储 X 坐标的字段名（应为东坐标）
    bank_y_field : str
        实测河岸点中存储 Y 坐标的字段名（应为北坐标）
    bank_z_field : str
        实测河岸点中存储 Z 坐标的字段名
    profile_x_field : str
        剖面点中存储 X 坐标的字段名
    profile_y_field : str
        剖面点中存储 Y 坐标的字段名
    profile_z_field : str
        剖面点中存储 Z 坐标的字段名
    profile_id_field : str
        剖面点中存储原始ID的字段名（应包含数字，如 "NTH035"，数字部分将被提取为剖面编号）
    """
    # 确保输出目录存在
    for path in [
        output_shoreline,
        output_left_bank_points,
        output_right_bank_points,
        output_profile_points,
        output_channel_polygon
    ]:
        os.makedirs(os.path.dirname(path), exist_ok=True)

    # ------------------------------------------------------------------
    # 1. 处理河岸线：读取、确定左右岸、添加 id 字段
    # ------------------------------------------------------------------
    gdf_shore = gpd.read_file(input_shoreline)
    if len(gdf_shore) != 2:
        raise ValueError("河岸线文件必须恰好包含两条线")

    lines = list(gdf_shore.geometry)
    for i, geom in enumerate(lines):
        if geom.geom_type == 'MultiLineString':
            lines[i] = geom.geoms[0]
            warnings.warn(f"第{i+1}条线是 MultiLineString，已使用其第一条子线")

    # 利用剖面点估计河流流向（用于判断左右岸）
    gdf_profile_raw = gpd.read_file(input_profile_points)
    if len(gdf_profile_raw) == 0:
        raise ValueError("剖面点文件为空，无法确定河流流向")

    # 提取剖面点坐标及原始ID
    xs = gdf_profile_raw[profile_x_field].astype(float)
    ys = gdf_profile_raw[profile_y_field].astype(float)
    zs = gdf_profile_raw[profile_z_field].astype(float)
    raw_ids = gdf_profile_raw[profile_id_field].astype(str)

    # 从原始ID中提取数字作为剖面编号 i
    profile_numbers = []
    for rid in raw_ids:
        nums = re.findall(r'\d+', rid)
        if not nums:
            raise ValueError(f"无法从ID字段值 '{rid}' 中提取数字，无法确定剖面编号")
        profile_numbers.append(int(nums[0]))

    # 构建临时DataFrame便于分组（用于计算每个剖面的中心点）
    df_profile = pd.DataFrame({
        'i': profile_numbers,
        'x': xs,
        'y': ys,
        'z': zs
    })

    # 按 i 分组，计算每个剖面的中心点
    centers = []
    for i, group in df_profile.groupby('i'):
        cx = group['x'].mean()
        cy = group['y'].mean()
        centers.append((i, cx, cy))

    # 按 i 排序（假设 i 沿河流方向单调）
    centers.sort(key=lambda x: x[0])
    if len(centers) < 2:
        raise ValueError("剖面数量少于2，无法确定河流流向")

    # 流向向量：从第一个剖面中心指向最后一个剖面中心
    start = np.array([centers[0][1], centers[0][2]])
    end = np.array([centers[-1][1], centers[-1][2]])
    flow_dir = end - start
    if np.linalg.norm(flow_dir) == 0:
        raise ValueError("剖面中心点重合，无法确定流向")
    flow_dir = flow_dir / np.linalg.norm(flow_dir)

    # 计算两条线的中心点
    def line_center(line):
        coords = np.array(line.coords)
        return coords.mean(axis=0)

    center0 = line_center(lines[0])
    center1 = line_center(lines[1])
    river_center = (center0 + center1) / 2

    # 左侧垂直向量（面向流向时左边）
    left_vec = np.array([-flow_dir[1], flow_dir[0]])

    # 判断每条线位于左侧还是右侧
    vec0 = center0 - river_center
    vec1 = center1 - river_center
    side0 = np.dot(vec0, left_vec)
    side1 = np.dot(vec1, left_vec)

    # 分配左右岸 id：左岸=0，右岸=1
    if side0 > side1:
        left_line, right_line = lines[0], lines[1]
    else:
        left_line, right_line = lines[1], lines[0]

    # 创建输出河岸线GeoDataFrame
    gdf_shore_out = gpd.GeoDataFrame({
        'id': [0, 1],
        'geometry': [left_line, right_line]
    }, crs=gdf_shore.crs)
    gdf_shore_out.to_file(output_shoreline, encoding='utf-8')

    # ------------------------------------------------------------------
    # 1.1 生成河道边界面（Polygon）
    # ------------------------------------------------------------------

    left_coords = list(left_line.coords)
    right_coords = list(right_line.coords)

    # 【新增修复逻辑】：判断左右岸线数字化（绘制）方向是否一致
    # 比较“左岸起点到右岸起点”的距离 与 “左岸起点到右岸终点”的距离
    pt_left_start = np.array(left_coords[0])
    pt_right_start = np.array(right_coords[0])
    pt_right_end = np.array(right_coords[-1])

    dist_start2start = np.linalg.norm(pt_left_start - pt_right_start)
    dist_start2end = np.linalg.norm(pt_left_start - pt_right_end)

    if dist_start2start > dist_start2end:
        # 如果左岸起点离右岸终点更近，说明原始两条河岸线的绘制方向相反
        # 此时需要翻转右岸点序，强制其与左岸方向一致
        right_coords = right_coords[::-1]

    # 右岸反向拼接形成闭合环（此时 left_coords 和 right_coords 走向必定一致）
    # 拼接逻辑：左岸起点 -> 左岸终点 -> 右岸终点 -> 右岸起点
    ring_coords = left_coords + right_coords[::-1]

    # 确保闭合
    if ring_coords[0] != ring_coords[-1]:
        ring_coords.append(ring_coords[0])

    channel_polygon = Polygon(ring_coords)

    gdf_channel = gpd.GeoDataFrame(
        {'id': [1]},
        geometry=[channel_polygon],
        crs=gdf_shore.crs
    )

    gdf_channel.to_file(output_channel_polygon, encoding='utf-8')

    logger.info("河道边界面生成完成。")

    # ------------------------------------------------------------------
    # 2. 处理河岸点：读取、归类、排序、生成新ID，分别输出左右岸文件
    # ------------------------------------------------------------------
    gdf_bank = gpd.read_file(input_bank_points)
    if len(gdf_bank) > 0:
        bank_x = gdf_bank[bank_x_field].astype(float)
        bank_y = gdf_bank[bank_y_field].astype(float)
        bank_z = gdf_bank[bank_z_field].astype(float)
        temp_points = [Point(x, y) for x, y in zip(bank_x, bank_y)]

        # 将岸线端点调整为最东北方向（用于排序方向）
        def orient_line_to_northeast(line):
            coords = list(line.coords)
            if len(coords) < 2:
                return line
            score0 = coords[0][0] + coords[0][1]
            score1 = coords[-1][0] + coords[-1][1]
            if score1 > score0:
                return LineString(coords[::-1])
            else:
                return line

        left_line_oriented = orient_line_to_northeast(left_line)
        right_line_oriented = orient_line_to_northeast(right_line)

        left_points = []   # (idx, proj_dist)
        right_points = []  # (idx, proj_dist)

        for idx, pt in enumerate(temp_points):
            dist_left = left_line_oriented.distance(pt)
            dist_right = right_line_oriented.distance(pt)
            if dist_left <= dist_right:
                proj_dist = left_line_oriented.project(pt)
                left_points.append((idx, proj_dist))
            else:
                proj_dist = right_line_oriented.project(pt)
                right_points.append((idx, proj_dist))

        # 按投影距离排序
        left_points.sort(key=lambda x: x[1])
        right_points.sort(key=lambda x: x[1])

        # 生成左岸点文件
        if left_points:
            left_idx = [p[0] for p in left_points]
            left_ids = [f"{order:03d}" for order, _ in enumerate(left_points, start=1)]
            left_gdf = gpd.GeoDataFrame({
                'x': bank_x.iloc[left_idx].values,
                'y': bank_y.iloc[left_idx].values,
                'z': bank_z.iloc[left_idx].values,
                'id': left_ids,
                'geometry': [temp_points[i] for i in left_idx]
            }, crs=gdf_bank.crs)
        else:
            left_gdf = gpd.GeoDataFrame(columns=['x','y','z','id','geometry'], crs=gdf_bank.crs)
        left_gdf.to_file(output_left_bank_points, encoding='utf-8')

        # 生成右岸点文件
        if right_points:
            right_idx = [p[0] for p in right_points]
            right_ids = [f"{order:03d}" for order, _ in enumerate(right_points, start=1)]
            right_gdf = gpd.GeoDataFrame({
                'x': bank_x.iloc[right_idx].values,
                'y': bank_y.iloc[right_idx].values,
                'z': bank_z.iloc[right_idx].values,
                'id': right_ids,
                'geometry': [temp_points[i] for i in right_idx]
            }, crs=gdf_bank.crs)
        else:
            right_gdf = gpd.GeoDataFrame(columns=['x','y','z','id','geometry'], crs=gdf_bank.crs)
        right_gdf.to_file(output_right_bank_points, encoding='utf-8')
    else:
        # 如果没有河岸点，创建空文件
        empty_gdf = gpd.GeoDataFrame(columns=['x','y','z','id','geometry'], crs=gdf_bank.crs)
        empty_gdf.to_file(output_left_bank_points, encoding='utf-8')
        empty_gdf.to_file(output_right_bank_points, encoding='utf-8')

    # ------------------------------------------------------------------
    # 3. 处理剖面点：从原始ID提取数字作为剖面编号 i，自动生成点序号 j
    # ------------------------------------------------------------------
    if len(gdf_profile_raw) > 0:
        # 使用之前提取的 profile_numbers (i) 和坐标
        profile_groups = {}  # key=i, value=list of (point_index, x, y, z)
        for idx, i in enumerate(profile_numbers):
            profile_groups.setdefault(i, []).append((idx, xs[idx], ys[idx], zs[idx]))

        # 为每个剖面的点分配 j（按原始索引顺序）
        new_profile_ids = [None] * len(gdf_profile_raw)
        for i, points in profile_groups.items():
            points.sort(key=lambda x: x[0])
            for j, (idx, x, y, z) in enumerate(points, start=1):
                new_profile_ids[idx] = f"{i:03d}_{j:03d}"   # 格式：剖面号三位，点号两位

        # 创建输出剖面点GeoDataFrame
        profile_geoms = [Point(x, y) for x, y in zip(xs, ys)]
        gdf_profile_out = gpd.GeoDataFrame({
            'x': xs,
            'y': ys,
            'z': zs,
            'id': new_profile_ids,
            'geometry': profile_geoms
        }, crs=gdf_profile_raw.crs)
    else:
        gdf_profile_out = gpd.GeoDataFrame(columns=['x','y','z','id','geometry'], crs=gdf_profile_raw.crs)

    gdf_profile_out.to_file(output_profile_points, encoding='utf-8')

    logger.info("数据预处理模块完成。")
    return

def main():
    input_shoreline = "../data/raw_data/河岸线.shp"
    input_bank_points = "../data/raw_data/实测河岸点.shp"
    input_profile_points = "../data/raw_data/剖面点.shp"

    output_shoreline = "../data/intermediate_data/河岸线.shp"
    output_left_bank_points = "../data/intermediate_data/左河岸点.shp"
    output_right_bank_points = "../data/intermediate_data/右河岸点.shp"
    output_profile_points = "../data/intermediate_data/剖面点.shp"
    output_channel_polygon = "../data/intermediate_data/河道边界.shp"

    # 字段名配置（请根据实际数据调整）
    bank_x_field = "东坐标"
    bank_y_field = "北坐标"
    bank_z_field = "高程"
    profile_x_field = "东坐标"
    profile_y_field = "北坐标"
    profile_z_field = "水底大"
    profile_id_field = "Type"

    try:
        preprocess_data(
            input_shoreline,
            input_bank_points,
            input_profile_points,
            output_shoreline,
            output_left_bank_points,
            output_right_bank_points,
            output_profile_points,
            output_channel_polygon,
            bank_x_field,
            bank_y_field,
            bank_z_field,
            profile_x_field,
            profile_y_field,
            profile_z_field,
            profile_id_field
        )
        logger.info("预处理完成！")
    except Exception as e:
        logger.error(f"预处理失败：{e}")

if __name__ == "__main__":
    main()