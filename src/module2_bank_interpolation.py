import os
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString
import warnings
import logging

# 忽略 geopandas/shapely 的一些非重要警告信息
warnings.filterwarnings("ignore", category=UserWarning)

# 引入已有的高程内插函数
try:
    from utils import interpolate_z_along_curve
except ImportError:
    raise ImportError("未能导入 utils 模块，请确保 utils.py 与此脚本在同一目录下。")

# 导入RC3DR日志系统，提供回退机制
try:
    from logger import get_module_logger
    logger = get_module_logger('module2')
except ImportError:
    # 回退到标准logging
    logger = logging.getLogger('rc3dr.module2')
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_normal_vector(line: LineString, point: Point, delta: float = 0.5) -> tuple:
    """
    计算线状要素上某点的法向量（用于作垂线）。
    """
    # 获取点在曲线上的投影距离
    dist = line.project(point)

    # 获取前后的点以计算切向量
    dist_prev = max(0, dist - delta)
    dist_next = min(line.length, dist + delta)

    pt_prev = line.interpolate(dist_prev)
    pt_next = line.interpolate(dist_next)

    # 切向量 (tx, ty)
    tx = pt_next.x - pt_prev.x
    ty = pt_next.y - pt_prev.y
    length = np.hypot(tx, ty)

    if length == 0:
        return (0.0, 0.0)

    # 单位化
    tx /= length
    ty /= length

    # 法向量 (nx, ny) - 逆时针旋转90度
    nx, ny = -ty, tx
    return nx, ny


def get_closest_valid_point(intersections, origin_pt: Point, threshold: float):
    """
    从相交结果中提取距离原点最近且在阈值范围内的点。
    """
    intersect_pts = []
    if intersections.is_empty:
        return None
    elif isinstance(intersections, Point):
        intersect_pts = [intersections]
    elif intersections.geom_type == 'MultiPoint':
        intersect_pts = list(intersections.geoms)
    elif intersections.geom_type == 'GeometryCollection':
        intersect_pts = [geom for geom in intersections.geoms if isinstance(geom, Point)]

    closest_pt = None
    min_dist = float('inf')

    for ipt in intersect_pts:
        d = origin_pt.distance(ipt)
        if d <= threshold and d < min_dist:
            min_dist = d
            closest_pt = ipt

    return closest_pt


def process_bank_interpolation(
        thalweg_line_shp: str,
        thalweg_interp_shp: str,
        bank_lines_shp: str,
        left_bank_known_shp: str,
        right_bank_known_shp: str,
        left_bank_interp_shp: str,
        right_bank_interp_shp: str,
        distance_threshold: float = 500.0
) -> None:
    """
    执行河岸点的平面与高程内插处理。
    """
    logger.info(">>> 启动模块2：河岸点内插...")

    # ==========================================
    # 步骤 1：河岸点平面位置内插
    # ==========================================
    logger.info("1. 读取矢量数据进行平面相交分析...")

    # 1.1 读取深泓线并合并为单一几何体 (修复 DeprecationWarning，使用 union_all())
    tl_gdf = gpd.read_file(thalweg_line_shp)
    thalweg_line = tl_gdf.geometry.union_all() if hasattr(tl_gdf.geometry, 'union_all') else tl_gdf.geometry.unary_union

    if thalweg_line.geom_type == 'MultiLineString':
        from shapely.ops import linemerge
        thalweg_line = linemerge(thalweg_line)

    # 1.2 读取河岸线，严格根据 id 区分左右岸 (id=0:左岸, id=1:右岸)
    bl_gdf = gpd.read_file(bank_lines_shp)
    bl_gdf['id'] = bl_gdf['id'].astype(int)

    left_mask = bl_gdf[bl_gdf['id'] == 0].geometry
    right_mask = bl_gdf[bl_gdf['id'] == 1].geometry

    # 同样修复 DeprecationWarning 兼容性处理
    left_bank_line = left_mask.union_all() if hasattr(left_mask, 'union_all') else left_mask.unary_union
    right_bank_line = right_mask.union_all() if hasattr(right_mask, 'union_all') else right_mask.unary_union

    if left_bank_line.is_empty or right_bank_line.is_empty:
        raise ValueError("河岸线数据中未能成功提取出左岸(id=0)或右岸(id=1)，请检查数据！")

    # 1.3 读取深泓点内插
    tp_gdf = gpd.read_file(thalweg_interp_shp)

    valid_thalweg_indices = []
    left_interp_data = []
    right_interp_data = []

    # 1.4 遍历每个内插深泓点
    for row in tp_gdf.itertuples():
        pt = row.geometry
        pt_id = row.id
        idx = row.Index  # 获取原始索引

        # 获取法向量
        nx, ny = get_normal_vector(thalweg_line, pt)
        if nx == 0 and ny == 0:
            continue

        # 构造过该点的超长垂线段用于相交（长度需大于可能的单侧河道最大宽度）
        cs_len = distance_threshold * 2.0
        p1 = Point(pt.x + nx * cs_len, pt.y + ny * cs_len)
        p2 = Point(pt.x - nx * cs_len, pt.y - ny * cs_len)
        cross_section_line = LineString([p1, p2])

        # 分别与确定的左、右岸线求交
        left_intersections = cross_section_line.intersection(left_bank_line)
        right_intersections = cross_section_line.intersection(right_bank_line)

        # 获取合法阈值内的最近交点
        closest_left = get_closest_valid_point(left_intersections, pt, distance_threshold)
        closest_right = get_closest_valid_point(right_intersections, pt, distance_threshold)

        # 检验是否同时存在合格的左右岸点
        if closest_left is not None and closest_right is not None:
            valid_thalweg_indices.append(idx)

            left_interp_data.append({
                'id': pt_id, 'x': closest_left.x, 'y': closest_left.y, 'z': 0.0, 'geometry': closest_left
            })

            right_interp_data.append({
                'id': pt_id, 'x': closest_right.x, 'y': closest_right.y, 'z': 0.0, 'geometry': closest_right
            })

    # 1.5 根据有效的索引更新深泓点内插文件（删除不合规的点）
    tp_updated_gdf = tp_gdf.loc[valid_thalweg_indices].copy()
    tp_updated_gdf.to_file(thalweg_interp_shp, encoding='utf-8')
    logger.info(f"原深泓内插点总数 {len(tp_gdf)}，有效保留 {len(valid_thalweg_indices)} 个。已更新 {os.path.basename(thalweg_interp_shp)}。")

    # 1.6 构建左右河岸内插点的 GeoDataFrame
    crs = tp_gdf.crs
    left_interp_gdf = gpd.GeoDataFrame(left_interp_data, crs=crs)
    right_interp_gdf = gpd.GeoDataFrame(right_interp_data, crs=crs)

    # 确保字段顺序及包含 x, y, z, id
    fields_order = ['id', 'x', 'y', 'z', 'geometry']
    left_interp_gdf = left_interp_gdf[fields_order]
    right_interp_gdf = right_interp_gdf[fields_order]

    # 保存平面的初次内插点
    left_interp_gdf.to_file(left_bank_interp_shp, encoding='utf-8')
    right_interp_gdf.to_file(right_bank_interp_shp, encoding='utf-8')
    logger.info("左、右河岸点平面内插计算完毕。")

    # ==========================================
    # 步骤 2：河岸点高程内插 (调用 utils)
    # ==========================================
    logger.info("2. 调用 utils 进行高程三次样条内插...")

    logger.info("[处理左岸高程]")
    interpolate_z_along_curve(left_bank_known_shp, left_bank_interp_shp)

    logger.info("[处理右岸高程]")
    interpolate_z_along_curve(right_bank_known_shp, right_bank_interp_shp)

    logger.info(">>> 模块2：河岸点内插执行完毕！")


if __name__ == "__main__":
    DATA_DIR = "../data/intermediate_data"
    paths = {
        "thalweg_line_shp": os.path.join(DATA_DIR, "深泓线.shp"),
        "thalweg_interp_shp": os.path.join(DATA_DIR, "深泓点内插.shp"),
        "bank_lines_shp": os.path.join(DATA_DIR, "河岸线.shp"),
        "left_bank_known_shp": os.path.join(DATA_DIR, "左河岸点.shp"),
        "right_bank_known_shp": os.path.join(DATA_DIR, "右河岸点.shp"),
        "left_bank_interp_shp": os.path.join(DATA_DIR, "左河岸点内插.shp"),
        "right_bank_interp_shp": os.path.join(DATA_DIR, "右河岸点内插.shp"),
    }
    THRESHOLD = 300.0

    process_bank_interpolation(
        thalweg_line_shp=paths["thalweg_line_shp"],
        thalweg_interp_shp=paths["thalweg_interp_shp"],
        bank_lines_shp=paths["bank_lines_shp"],
        left_bank_known_shp=paths["left_bank_known_shp"],
        right_bank_known_shp=paths["right_bank_known_shp"],
        left_bank_interp_shp=paths["left_bank_interp_shp"],
        right_bank_interp_shp=paths["right_bank_interp_shp"],
        distance_threshold=THRESHOLD
    )