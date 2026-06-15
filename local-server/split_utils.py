#!/usr/bin/env python3
"""
图片分割工具模块 - 共享的图片分割逻辑
server.py 和 tray_service.py 都从这里导入
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_split_dir():
    """获取图片分割目录"""
    split_dir = Path(__file__).parent / "images" / "split"
    split_dir.mkdir(parents=True, exist_ok=True)
    return split_dir


def split_grid_image(img):
    """分割网格排列的图片"""
    import cv2
    import numpy as np
    
    height, width = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 二值化
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # 查找分割线
    h_lines = find_dividing_lines(binary, axis='horizontal', min_length=width*0.3)
    v_lines = find_dividing_lines(binary, axis='vertical', min_length=height*0.3)
    
    logger.info(f"[分割] 检测到 {len(h_lines)} 条水平分割线, {len(v_lines)} 条垂直分割线")
    
    # 计算网格区域
    regions = calculate_grid_regions(h_lines, v_lines, width, height, img=img)
    
    if not regions:
        # 尝试自动检测
        regions = auto_detect_grid(binary, width, height, img=img)
    
    # 裁剪每个区域
    result = []
    for x, y, w, h in regions:
        region = img[y:y+h, x:x+w]
        result.append(region)
    
    return result


def find_dividing_lines(binary, axis='horizontal', min_length=100, threshold=0.8):
    """查找分割线"""
    import numpy as np
    
    lines = []
    h, w = binary.shape
    
    if axis == 'horizontal':
        for y in range(h):
            row = binary[y, :]
            white_ratio = np.sum(row > 0) / w
            if white_ratio > threshold:
                if is_continuous_line(row, min_length):
                    lines.append(y)
    else:
        for x in range(w):
            col = binary[:, x]
            white_ratio = np.sum(col > 0) / h
            if white_ratio > threshold:
                if is_continuous_line(col, min_length):
                    lines.append(x)
    
    return merge_nearby_lines(lines, gap=5)


def is_continuous_line(pixels, min_length):
    """检查是否是连续的白色像素"""
    max_continuous = 0
    current = 0
    
    for p in pixels:
        if p > 0:
            current += 1
            max_continuous = max(max_continuous, current)
        else:
            current = 0
    
    return max_continuous >= min_length


def merge_nearby_lines(lines, gap=5):
    """合并相近的线"""
    if not lines:
        return []
    
    merged = [lines[0]]
    for line in lines[1:]:
        if line - merged[-1] <= gap:
            merged[-1] = (merged[-1] + line) // 2
        else:
            merged.append(line)
    
    return merged


def calculate_grid_regions(h_lines, v_lines, width, height, img=None, min_white_ratio=0.1):
    """根据分割线计算网格区域"""
    import cv2
    import numpy as np
    
    regions = []
    
    h_boundaries = [0] + h_lines + [height]
    v_boundaries = [0] + v_lines + [width]
    
    for i in range(len(h_boundaries) - 1):
        for j in range(len(v_boundaries) - 1):
            y1 = h_boundaries[i]
            y2 = h_boundaries[i + 1]
            x1 = v_boundaries[j]
            x2 = v_boundaries[j + 1]
            
            w = x2 - x1
            h = y2 - y1
            
            if w < 50 or h < 50:
                continue
            
            if img is not None:
                region = img[y1:y2, x1:x2]
                if is_black_region(region, threshold=30, white_ratio_threshold=min_white_ratio):
                    continue
            
            regions.append((x1, y1, w, h))
    
    return regions


def is_black_region(region, threshold=30, white_ratio_threshold=0.1):
    """检查区域是否是黑色/无效区域"""
    import cv2
    import numpy as np
    
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    
    white_pixels = np.sum(gray > 200)
    total_pixels = gray.size
    white_ratio = white_pixels / total_pixels
    
    mean_brightness = np.mean(gray)
    
    if white_ratio < white_ratio_threshold or mean_brightness < threshold:
        return True
    
    return False


def auto_detect_grid(binary, width, height, img=None):
    """自动检测网格"""
    import numpy as np
    
    h_proj = np.sum(binary, axis=1)
    v_proj = np.sum(binary, axis=0)
    
    h_splits = find_splits_from_projection(h_proj, threshold=np.max(h_proj)*0.1, min_gap=50)
    v_splits = find_splits_from_projection(v_proj, threshold=np.max(v_proj)*0.1, min_gap=50)
    
    h_boundaries = [0] + h_splits + [height]
    v_boundaries = [0] + v_splits + [width]
    
    regions = []
    for i in range(len(h_boundaries) - 1):
        for j in range(len(v_boundaries) - 1):
            y1 = h_boundaries[i]
            y2 = h_boundaries[i + 1]
            x1 = v_boundaries[j]
            x2 = v_boundaries[j + 1]
            
            w = x2 - x1
            h = y2 - y1
            
            if w < 50 or h < 50:
                continue
            
            if img is not None:
                region = img[y1:y2, x1:x2]
                if is_black_region(region, threshold=30, white_ratio_threshold=0.1):
                    continue
            
            regions.append((x1, y1, w, h))
    
    return regions


def find_splits_from_projection(projection, threshold, min_gap=50):
    """从投影中找到分割位置"""
    splits = []
    below_threshold = False
    start = 0
    
    for i, val in enumerate(projection):
        if val < threshold and not below_threshold:
            below_threshold = True
            start = i
        elif val >= threshold and below_threshold:
            below_threshold = False
            mid = (start + i) // 2
            if i - start >= 10:
                splits.append(mid)
    
    return merge_nearby_lines(splits, gap=min_gap)


def crop_black_edges(image, threshold=30, margin=2):
    """裁剪图片的黑色边缘和红色线条"""
    import cv2
    import numpy as np
    
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
    
    lower_red2 = np.array([160, 50, 50])
    upper_red2 = np.array([180, 255, 255])
    mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
    
    mask_red = mask_red1 | mask_red2
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask_black = gray > threshold
    
    mask_valid = mask_black & (mask_red == 0)
    
    rows = np.any(mask_valid, axis=1)
    cols = np.any(mask_valid, axis=0)
    
    if not np.any(rows) or not np.any(cols):
        return image
    
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    
    rmin = max(0, rmin - margin)
    rmax = min(image.shape[0] - 1, rmax + margin)
    cmin = max(0, cmin - margin)
    cmax = min(image.shape[1] - 1, cmax + margin)
    
    return image[rmin:rmax+1, cmin:cmax+1]

