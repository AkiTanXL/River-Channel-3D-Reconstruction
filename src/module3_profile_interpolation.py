import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
from scipy.interpolate import interp1d
import os
import warnings
import logging

try:
    from logger import get_module_logger, log_exception, log_progress

    logger = get_module_logger('module3')
except ImportError:
    logger = logging.getLogger('rc3dr.module3')
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

warnings.filterwarnings("ignore")


def parse_thalweg_id(id_str):
    parts = str(id_str).split('_')
    if len(parts) >= 3:
        return parts[0], parts[1], int(parts[2])
    return None, None, None


class ReferenceProfile:
    """实测剖面模型类 (高保真版)"""

    def __init__(self, profile_id, points_df):
        self.id = profile_id
        self.points_df = points_df
        self.thalweg_pt = None
        self.arms = []
        self._process_profile()

    def _process_profile(self):
        min_z_idx = self.points_df['z'].idxmin()
        row = self.points_df.loc[min_z_idx]
        self.thalweg_pt = np.array([row['x'], row['y'], row['z']])
        t_xy = self.thalweg_pt[:2]

        # 【优化】向量化计算距离
        self.points_df['dist_temp'] = np.hypot(self.points_df['x'] - t_xy[0], self.points_df['y'] - t_xy[1])
        candidates = self.points_df[self.points_df['dist_temp'] > 0.1]
        if candidates.empty:
            self.arms = [None, None]
            return

        idx_far1 = candidates['dist_temp'].idxmax()
        pt_far1 = candidates.loc[idx_far1]
        vec_far1 = np.array([pt_far1['x'], pt_far1['y']]) - t_xy

        # 【优化】使用向量化点积分离两岸
        vecs = np.c_[self.points_df['x'] - t_xy[0], self.points_df['y'] - t_xy[1]]
        dots = vecs.dot(vec_far1)

        # 排除深泓点自身
        mask_not_thalweg = self.points_df.index != min_z_idx
        arm1_indices = self.points_df.index[mask_not_thalweg & (dots >= 0)].tolist()
        arm2_indices = self.points_df.index[mask_not_thalweg & (dots < 0)].tolist()

        self.arms = [
            self._build_high_fidelity_arm(arm1_indices),
            self._build_high_fidelity_arm(arm2_indices)
        ]

    def _build_high_fidelity_arm(self, indices):
        if not indices: return None
        df_arm = self.points_df.loc[indices].copy()
        t_xy, t_z = self.thalweg_pt[:2], self.thalweg_pt[2]

        idx_bank = df_arm['dist_temp'].idxmax()
        bank_pt = df_arm.loc[idx_bank]
        b_xy, b_z = np.array([bank_pt['x'], bank_pt['y']]), bank_pt['z']

        axis_vec = b_xy - t_xy
        max_dist = np.linalg.norm(axis_vec)
        if max_dist == 0: return None
        axis_unit = axis_vec / max_dist

        vecs = np.c_[df_arm['x'] - t_xy[0], df_arm['y'] - t_xy[1]]
        proj_dists = vecs.dot(axis_unit)

        valid_mask = proj_dists > 0
        valid_dists = proj_dists[valid_mask]
        valid_zs = df_arm['z'].values[valid_mask]

        all_dists = np.concatenate(([0.0], valid_dists))
        all_zs = np.concatenate(([t_z], valid_zs))

        sort_idx = np.argsort(all_dists)
        dists_sorted, zs_sorted = all_dists[sort_idx], all_zs[sort_idx]

        z_diff = b_z - t_z
        r_list = dists_sorted / max_dist

        if abs(z_diff) < 0.01:
            rz_list = np.zeros_like(zs_sorted)
        else:
            rz_list = (zs_sorted - t_z) / z_diff

        r_list[-1], rz_list[-1] = 1.0, 1.0
        # 允许接收 numpy array 输入
        func = interp1d(r_list, rz_list, kind='linear', bounds_error=False, fill_value=(0, 1))
        return {'func': func, 'vec': axis_vec, 'z_diff': z_diff}


def interpolate_profiles(thalweg_line_path, thalweg_pts_path, left_bank_pts_path, right_bank_pts_path,
                         measured_profile_path, output_path, step_size=2.0):
    logger.info("正在加载数据...")
    gdf_thalweg = gpd.read_file(thalweg_pts_path)
    gdf_left_bank = gpd.read_file(left_bank_pts_path)
    gdf_right_bank = gpd.read_file(right_bank_pts_path)
    gdf_measured = gpd.read_file(measured_profile_path)

    logger.info("正在建立实测剖面形态模型...")
    ref_profiles = {}
    gdf_measured['ProfileID'] = gdf_measured['id'].apply(lambda x: str(x).split('_')[0])
    if 'x' not in gdf_measured.columns:
        gdf_measured['x'], gdf_measured['y'] = gdf_measured.geometry.x, gdf_measured.geometry.y

    for name, group in gdf_measured.groupby('ProfileID'):
        ref_profiles[name] = ReferenceProfile(name, group)
    logger.info(f"已构建 {len(ref_profiles)} 个实测剖面模型")

    # 【优化】将左右岸转化为快速查找字典 (itertuples 比 iterrows 快几十倍)
    left_bank_dict = {row.id: row for row in gdf_left_bank.itertuples(index=False)}
    right_bank_dict = {row.id: row for row in gdf_right_bank.itertuples(index=False)}

    logger.info("计算接缝高程校正参数...")
    segment_corrections = {}
    if 'id' in gdf_thalweg.columns:
        gdf_thalweg['SegmentID'] = gdf_thalweg['id'].apply(lambda val: "_".join(str(val).split('_')[:2]))
        for seg_id, group in gdf_thalweg.groupby('SegmentID'):
            parts = seg_id.split('_')
            up_id, down_id = parts[0], parts[1]
            if up_id not in ref_profiles or down_id not in ref_profiles: continue

            group = group.sort_values('id')
            t_model_start, t_model_end = group.iloc[0]['z'], group.iloc[-1]['z']
            t_real_start, t_real_end = ref_profiles[up_id].thalweg_pt[2], ref_profiles[down_id].thalweg_pt[2]
            segment_corrections[seg_id] = {
                'dt_start': t_real_start - t_model_start,
                'dt_end': t_real_end - t_model_end,
                'count': len(group)
            }

    logger.info("开始生成剖面点 (高性能矩阵运算模式)...")
    output_points = []
    gdf_thalweg = gdf_thalweg.sort_values('id').reset_index(drop=True)
    count, total = 0, len(gdf_thalweg)

    # 【优化】使用 itertuples 替代 iterrows
    for t_row in gdf_thalweg.itertuples(index=False):
        t_id, t_geom, t_z_raw = t_row.id, t_row.geometry, t_row.z
        up_id, down_id, curr_num = parse_thalweg_id(t_id)
        if not up_id or up_id not in ref_profiles or down_id not in ref_profiles: continue

        ref_up, ref_down = ref_profiles[up_id], ref_profiles[down_id]
        seg_id = f"{up_id}_{down_id}"
        ratio, delta_t_corr = 0.5, 0.0

        if seg_id in segment_corrections:
            info = segment_corrections[seg_id]
            ratio = max(0.0, min(1.0, (curr_num - 1) / (info['count'] - 1) if info['count'] > 1 else 0.0))
            delta_t_corr = info['dt_start'] * (1 - ratio) + info['dt_end'] * ratio

        w_up, w_down = 1.0 - ratio, ratio
        t_z_final = t_z_raw + delta_t_corr

        output_points.append({
            'x': t_geom.x, 'y': t_geom.y, 'z': t_z_raw,
            'BaseID': t_id, 'Side': 'thalweg', 'Dist': 0.0
        })

        def process_side(bank_row, side_name):
            b_geom, b_z_raw = bank_row.geometry, bank_row.z
            target_vec = np.array([b_geom.x - t_geom.x, b_geom.y - t_geom.y])

            def get_best_model(ref_prof, vec):
                best_arm, max_score = None, -float('inf')
                for arm in ref_prof.arms:
                    if arm is None: continue
                    score = np.dot(vec, arm['vec'])
                    if score > max_score: max_score, best_arm = score, arm
                return best_arm

            model_up = get_best_model(ref_up, target_vec)
            model_down = get_best_model(ref_down, target_vec)
            model_up = model_up or model_down
            model_down = model_down or model_up
            if not model_up: return

            b_z_final_ref = b_z_raw + delta_t_corr
            total_len = t_geom.distance(b_geom)

            output_points.append({
                'x': b_geom.x, 'y': b_geom.y, 'z': b_z_raw,
                'BaseID': t_id, 'Side': side_name, 'Dist': total_len
            })

            if total_len <= 0.1: return

            # 【核心优化】：消除 while 循环，使用 NumPy 向量化生成坐标与高程
            dists_arr = np.arange(step_size, total_len - 0.1, step_size)
            if len(dists_arr) == 0: return

            dx, dy = b_geom.x - t_geom.x, b_geom.y - t_geom.y
            r_dists = dists_arr / total_len
            interp_x = t_geom.x + dx * r_dists
            interp_y = t_geom.y + dy * r_dists

            rz_up = model_up['func'](r_dists)
            rz_down = model_down['func'](r_dists)
            rz_mixed = rz_up * w_up + rz_down * w_down
            final_zs = t_z_final + rz_mixed * (b_z_final_ref - t_z_final)

            # 批量合并结果 (避免百万级的单一字典append)
            batch = [{'x': x, 'y': y, 'z': z, 'BaseID': t_id, 'Side': side_name, 'Dist': d}
                     for x, y, z, d in zip(interp_x, interp_y, final_zs, dists_arr)]
            output_points.extend(batch)

        if t_id in left_bank_dict: process_side(left_bank_dict[t_id], 'left')
        if t_id in right_bank_dict: process_side(right_bank_dict[t_id], 'right')

        count += 1
        if count % 200 == 0: logger.info(f"已处理 {count}/{total} 个断面")

    if not output_points: raise ValueError("未生成任何内插点。")

    logger.info("正在执行高效点云编排与输出...")
    df_out = pd.DataFrame(output_points)

    # 【核心优化】：放弃耗时的 groupby.iterrows 拼接，使用 Pandas 原生排序与批量运算
    # 左右侧逻辑映射：左侧为0，深泓为1，右侧为2
    side_order = {'left': 0, 'thalweg': 1, 'right': 2}
    df_out['SideOrder'] = df_out['Side'].map(side_order)

    # 距离排序逻辑：左岸点距离越远排在越前（加负号逆转），右岸点正常按距离升序
    df_out['SortDist'] = df_out['Dist']
    df_out.loc[df_out['Side'] == 'left', 'SortDist'] = -df_out['Dist']

    # 执行一次性全局排序
    df_out = df_out.sort_values(['BaseID', 'SideOrder', 'SortDist'])

    # 使用 cumcount 瞬间生成组内序号
    df_out['point_idx'] = df_out.groupby('BaseID').cumcount() + 1
    df_out['id'] = df_out['BaseID'].astype(str) + "_" + df_out['point_idx'].astype(str).str.zfill(3)

    # 向量化生成几何列
    gdf_final = gpd.GeoDataFrame(
        df_out[['id', 'x', 'y', 'z']],
        geometry=gpd.points_from_xy(df_out['x'], df_out['y'], df_out['z']),
        crs=gdf_thalweg.crs
    )

    out_dir = os.path.dirname(output_path)
    if out_dir: os.makedirs(out_dir, exist_ok=True)
    gdf_final.to_file(output_path, driver='ESRI Shapefile', encoding='utf-8')
    logger.info(f"剖面点内插完成: {output_path}")


def run_profile_interpolation(thalweg_line_path, thalweg_pts_path, left_bank_pts_path, right_bank_pts_path,
                              measured_profile_path, output_path, step_size=2.0):
    logger.info("=" * 45)
    logger.info(">>> 启动模块3: 剖面点内插 <<<")
    try:
        interpolate_profiles(thalweg_line_path, thalweg_pts_path, left_bank_pts_path, right_bank_pts_path,
                             measured_profile_path, output_path, step_size)
        logger.info(">>> 模块3执行完毕！ <<<")
        logger.info("=" * 45)
    except Exception as e:
        log_exception(logger, e, "模块3执行失败")
        raise