import os
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
from scipy.interpolate import PchipInterpolator  # 引入保形插值，防止过冲
import logging

# 导入公共库中的高程内插函数
from utils import interpolate_z_along_curve

# 导入RC3DR日志系统，提供回退机制
try:
    from logger import get_module_logger
    logger = get_module_logger('module1')
except ImportError:
    # 回退到标准logging
    logger = logging.getLogger('rc3dr.module1')
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_river_axis(banks_shp: str, axis_shp: str) -> LineString:
    """
    1. 河道轴线获取：基于“引导线 + 严格中线捕捉”算法提取绝对不与河岸相交的平滑中轴线。
    """
    logger.info("1. 正在生成高精度河道轴线...")
    banks_gdf = gpd.read_file(banks_shp)

    lines = []
    for geom in banks_gdf.geometry:
        if geom.geom_type == 'LineString':
            lines.append(geom)
        elif geom.geom_type == 'MultiLineString':
            lines.extend(list(geom.geoms))

    if len(lines) < 2:
        raise ValueError("河岸线shp文件中未找到两条折线！")

    bank1, bank2 = lines[0], lines[1]

    p1_start, p1_end = Point(bank1.coords[0]), Point(bank1.coords[-1])
    p2_start, p2_end = Point(bank2.coords[0]), Point(bank2.coords[-1])

    if p1_start.distance(p2_start) > p1_start.distance(p2_end):
        bank2 = LineString(list(bank2.coords)[::-1])

    num_guide_points = 1000
    distances = np.linspace(0, 1, num_guide_points)
    rough_coords = []
    for d in distances:
        pt1 = bank1.interpolate(d, normalized=True)
        pt2 = bank2.interpolate(d, normalized=True)
        rough_coords.append(((pt1.x + pt2.x) / 2.0, (pt1.y + pt2.y) / 2.0))
    rough_line = LineString(rough_coords)

    num_final_points = max(2000, int(rough_line.length / 2.0))
    distances_final = np.linspace(0, rough_line.length, num_final_points)

    medial_coords = []
    for d in distances_final:
        p_rough = rough_line.interpolate(d)

        proj_dist1 = bank1.project(p_rough)
        p1 = bank1.interpolate(proj_dist1)

        proj_dist2 = bank2.project(p_rough)
        p2 = bank2.interpolate(proj_dist2)

        mx, my = (p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0
        medial_coords.append((mx, my))

    def moving_average(coords, window_size):
        if len(coords) < window_size:
            return coords
        x = np.array([c[0] for c in coords])
        y = np.array([c[1] for c in coords])
        pad_w = window_size // 2
        x_pad = np.pad(x, (pad_w, window_size - 1 - pad_w), mode='edge')
        y_pad = np.pad(y, (pad_w, window_size - 1 - pad_w), mode='edge')
        x_smooth = np.convolve(x_pad, np.ones(window_size) / window_size, mode='valid')
        y_smooth = np.convolve(y_pad, np.ones(window_size) / window_size, mode='valid')
        return list(zip(x_smooth, y_smooth))

    smooth_coords = moving_average(medial_coords, window_size=30)
    axis_line = LineString(smooth_coords)
    axis_line = axis_line.simplify(0.5, preserve_topology=True)

    axis_gdf = gpd.GeoDataFrame([{'geometry': axis_line}], crs=banks_gdf.crs)
    axis_gdf.to_file(axis_shp, encoding='utf-8')
    logger.info(f"河道轴线已保存至: {axis_shp}")
    return axis_line


def extract_thalweg_points(profile_pts_shp: str, thalweg_pts_shp: str) -> gpd.GeoDataFrame:
    """
    2. 深泓点提取：获取各剖面最低点，更新id并输出。
    """
    logger.info("2. 正在提取深泓点...")
    pts_gdf = gpd.read_file(profile_pts_shp)

    if 'id' not in pts_gdf.columns or 'z' not in pts_gdf.columns:
        raise ValueError("剖面点属性必须包含 'id' 和 'z' 字段！")

    pts_gdf['sec_id'] = pts_gdf['id'].astype(str).str[:3]
    min_z_indices = pts_gdf.groupby('sec_id')['z'].idxmin()
    thalweg_pts = pts_gdf.loc[min_z_indices].copy()

    thalweg_pts['id'] = thalweg_pts['sec_id']
    thalweg_pts = thalweg_pts[['id', 'x', 'y', 'z', 'geometry']]
    thalweg_pts = thalweg_pts.sort_values('id').reset_index(drop=True)

    thalweg_pts['geometry'] = thalweg_pts.apply(
        lambda row: Point(row['x'], row['y'], row['z']), axis=1
    )

    thalweg_pts.to_file(thalweg_pts_shp, encoding='utf-8')
    logger.info(f"共提取 {len(thalweg_pts)} 个深泓点，已保存至: {thalweg_pts_shp}")
    return thalweg_pts


def generate_thalweg_line_and_interpolate(axis_line: LineString, thalweg_pts: gpd.GeoDataFrame,
                                          step: float, thalweg_line_shp: str, interp_pts_shp: str):
    """
    3. 深泓线生成及平面位置内插
    """
    logger.info("3. 正在生成深泓线并进行平面内插...")

    s_vals = []
    offsets = []

    # 获取每个深泓点在轴线上的里程和侧向偏置量
    for geom in thalweg_pts.geometry:
        s_proj = axis_line.project(geom)
        s_vals.append(s_proj)
        p_axis = axis_line.interpolate(s_proj)

        # 扩大法向计算的基线长度（避免局部微小锯齿导致法向突变打折）
        delta_s = min(5.0, axis_line.length / 1000.0)
        p_prev = axis_line.interpolate(max(0, s_proj - delta_s))
        p_next = axis_line.interpolate(min(axis_line.length, s_proj + delta_s))

        dx = p_next.x - p_prev.x
        dy = p_next.y - p_prev.y
        length = np.hypot(dx, dy)

        if length == 0:
            nx, ny = 0, 0
        else:
            nx, ny = -dy / length, dx / length

        offset = (geom.x - p_axis.x) * nx + (geom.y - p_axis.y) * ny
        offsets.append(offset)

    s_vals = np.array(s_vals)
    offsets = np.array(offsets)

    sort_idx = np.argsort(s_vals)
    s_vals, offsets = s_vals[sort_idx], offsets[sort_idx]
    sorted_thalweg_pts = thalweg_pts.iloc[sort_idx].reset_index(drop=True)

    # 【优化1】：使用 PchipInterpolator 替换 CubicSpline，彻底消除过冲引起的打折转圈
    pchip_offset = PchipInterpolator(s_vals, offsets)

    # 密集生成节点
    dense_s = np.linspace(max(0, s_vals[0] - 20), min(axis_line.length, s_vals[-1] + 20),
                          max(2000, int(axis_line.length / (step / 2))))
    base_offsets = pchip_offset(dense_s)

    # 【优化2】：引入“轴线引力”衰减机制，解决“贴合度不够”的问题
    # 目的：在远离已知深泓点的空白区域，强制让偏置量向 0 衰减，从而紧密逼近河道轴线
    final_offsets = []
    for s, b_off in zip(dense_s, base_offsets):
        if s <= s_vals[0] or s >= s_vals[-1]:
            final_offsets.append(b_off)  # 首尾外延段保持不变
            continue

        # 找到当前 s 所属的区间
        idx = np.searchsorted(s_vals, s) - 1
        s_left, s_right = s_vals[idx], s_vals[idx + 1]

        # 计算在该区间内的相对位置比例 t (0~1)
        L = s_right - s_left
        t = (s - s_left) / L if L > 0 else 0

        # 构造向心衰减包络线 (两端为1，中间为最低点)。0.8代表最大收缩程度，越大在中间越贴合轴线
        shrink_strength = 0.85
        envelope = 1.0 - (4.0 * shrink_strength * t * (1.0 - t))

        final_offsets.append(b_off * envelope)

    # 根据法向量生成深泓线坐标
    thalweg_coords = []
    delta_s = min(2.0, axis_line.length / 2000.0)
    for s, off in zip(dense_s, final_offsets):
        p_axis = axis_line.interpolate(s)
        p_prev = axis_line.interpolate(max(0, s - delta_s))
        p_next = axis_line.interpolate(min(axis_line.length, s + delta_s))
        dx, dy = p_next.x - p_prev.x, p_next.y - p_prev.y
        l = np.hypot(dx, dy)
        if l == 0:
            thalweg_coords.append((p_axis.x, p_axis.y))
        else:
            nx, ny = -dy / l, dx / l
            thalweg_coords.append((p_axis.x + off * nx, p_axis.y + off * ny))

    # 【优化3】：再次对生成的深泓线坐标进行轻微的平滑处理，熨平最后的微小折角
    def moving_average_coords(coords, window=10):
        if len(coords) < window: return coords
        x, y = np.array([c[0] for c in coords]), np.array([c[1] for c in coords])
        pw = window // 2
        x_p = np.pad(x, (pw, window - 1 - pw), mode='edge')
        y_p = np.pad(y, (pw, window - 1 - pw), mode='edge')
        x_s = np.convolve(x_p, np.ones(window) / window, mode='valid')
        y_s = np.convolve(y_p, np.ones(window) / window, mode='valid')
        # 强制替换首尾，保证精准穿过第一个和最后一个深泓点
        x_s[0], y_s[0] = x[0], y[0]
        x_s[-1], y_s[-1] = x[-1], y[-1]
        return list(zip(x_s, y_s))

    smooth_coords = moving_average_coords(thalweg_coords, window=15)
    smooth_thalweg_line = LineString(smooth_coords)

    line_gdf = gpd.GeoDataFrame([{'geometry': smooth_thalweg_line}], crs=thalweg_pts.crs)
    line_gdf.to_file(thalweg_line_shp, encoding='utf-8')
    logger.info(f"深泓线(保形抗过冲+向心贴合)生成完毕，已保存至: {thalweg_line_shp}")

    # ---- 3.2 沿生成的深泓线内插点 ----
    interp_records = []
    pts_s_on_curve = [smooth_thalweg_line.project(geom) for geom in sorted_thalweg_pts.geometry]

    for i in range(len(sorted_thalweg_pts) - 1):
        pt1 = sorted_thalweg_pts.iloc[i]
        pt2 = sorted_thalweg_pts.iloc[i + 1]
        id1, id2 = pt1['id'], pt2['id']

        s1 = pts_s_on_curve[i]
        s2 = pts_s_on_curve[i + 1]

        if s1 > s2:
            s1, s2 = s2, s1

        dense_s = np.arange(s1 + step, s2, step)

        for idx, current_s in enumerate(dense_s, start=1):
            new_pt = smooth_thalweg_line.interpolate(current_s)
            new_id = f"{id1}_{id2}_{idx:03d}"
            interp_records.append({
                'id': new_id,
                'x': new_pt.x,
                'y': new_pt.y,
                'z': 0.0,
                'geometry': Point(new_pt.x, new_pt.y)
            })

    interp_gdf = gpd.GeoDataFrame(interp_records, crs=thalweg_pts.crs)
    interp_gdf.to_file(interp_pts_shp, encoding='utf-8')
    logger.info(f"沿深泓线定步长({step})平面内插完毕，共生成 {len(interp_gdf)} 个点。")
    logger.info(f"结果已保存至: {interp_pts_shp}")


def run_module1(step_length: float, base_dir: str = "../data/intermediate_data"):
    """
    模块1主入口：执行深泓点内插四大步骤
    """
    logger.info("=" * 45)
    logger.info(">>> 启动模块1: 河道深泓点内插 <<<")

    banks_shp = os.path.join(base_dir, "河岸线.shp")
    profile_pts_shp = os.path.join(base_dir, "剖面点.shp")

    axis_shp = os.path.join(base_dir, "河道轴线.shp")
    thalweg_line_shp = os.path.join(base_dir, "深泓线.shp")
    thalweg_pts_shp = os.path.join(base_dir, "深泓点.shp")
    interp_pts_shp = os.path.join(base_dir, "深泓点内插.shp")

    axis_line = get_river_axis(banks_shp, axis_shp)
    thalweg_pts = extract_thalweg_points(profile_pts_shp, thalweg_pts_shp)

    generate_thalweg_line_and_interpolate(
        axis_line=axis_line,
        thalweg_pts=thalweg_pts,
        step=step_length,
        thalweg_line_shp=thalweg_line_shp,
        interp_pts_shp=interp_pts_shp
    )

    logger.info("4. 调用公共模块补全高程...")
    interpolate_z_along_curve(thalweg_pts_shp, interp_pts_shp)

    logger.info(">>> 模块1执行完毕！ <<<")
    logger.info("=" * 45)


if __name__ == "__main__":
    run_module1(step_length=5.0)