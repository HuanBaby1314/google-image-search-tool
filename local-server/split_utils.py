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


   626|def split_grid_image(img):
   627|    """分割网格排列的图片"""
   628|    import cv2
   629|    import numpy as np
   630|    
   631|    height, width = img.shape[:2]
   632|    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
   633|    
   634|    # 二值化
   635|    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
   636|    
   637|    # 查找分割线
   638|    h_lines = find_dividing_lines(binary, axis='horizontal', min_length=width*0.3)
   639|    v_lines = find_dividing_lines(binary, axis='vertical', min_length=height*0.3)
   640|    
   641|    logger.info(f"[分割] 检测到 {len(h_lines)} 条水平分割线, {len(v_lines)} 条垂直分割线")
   642|    
   643|    # 计算网格区域
   644|    regions = calculate_grid_regions(h_lines, v_lines, width, height, img=img)
   645|    
   646|    if not regions:
   647|        # 尝试自动检测
   648|        regions = auto_detect_grid(binary, width, height, img=img)
   649|    
   650|    # 裁剪每个区域
   651|    result = []
   652|    for x, y, w, h in regions:
   653|        region = img[y:y+h, x:x+w]
   654|        result.append(region)
   655|    
   656|    return result
   657|
   658|
   659|def find_dividing_lines(binary, axis='horizontal', min_length=100, threshold=0.8):
   660|    """查找分割线"""
   661|    import numpy as np
   662|    
   663|    lines = []
   664|    h, w = binary.shape
   665|    
   666|    if axis == 'horizontal':
   667|        for y in range(h):
   668|            row = binary[y, :]
   669|            white_ratio = np.sum(row > 0) / w
   670|            if white_ratio > threshold:
   671|                if is_continuous_line(row, min_length):
   672|                    lines.append(y)
   673|    else:
   674|        for x in range(w):
   675|            col = binary[:, x]
   676|            white_ratio = np.sum(col > 0) / h
   677|            if white_ratio > threshold:
   678|                if is_continuous_line(col, min_length):
   679|                    lines.append(x)
   680|    
   681|    return merge_nearby_lines(lines, gap=5)
   682|
   683|
   684|def is_continuous_line(pixels, min_length):
   685|    """检查是否是连续的白色像素"""
   686|    max_continuous = 0
   687|    current = 0
   688|    
   689|    for p in pixels:
   690|        if p > 0:
   691|            current += 1
   692|            max_continuous = max(max_continuous, current)
   693|        else:
   694|            current = 0
   695|    
   696|    return max_continuous >= min_length
   697|
   698|
   699|def merge_nearby_lines(lines, gap=5):
   700|    """合并相近的线"""
   701|    if not lines:
   702|        return []
   703|    
   704|    merged = [lines[0]]
   705|    for line in lines[1:]:
   706|        if line - merged[-1] <= gap:
   707|            merged[-1] = (merged[-1] + line) // 2
   708|        else:
   709|            merged.append(line)
   710|    
   711|    return merged
   712|
   713|
   714|def calculate_grid_regions(h_lines, v_lines, width, height, img=None, min_white_ratio=0.1):
   715|    """根据分割线计算网格区域"""
   716|    import cv2
   717|    import numpy as np
   718|    
   719|    regions = []
   720|    
   721|    h_boundaries = [0] + h_lines + [height]
   722|    v_boundaries = [0] + v_lines + [width]
   723|    
   724|    for i in range(len(h_boundaries) - 1):
   725|        for j in range(len(v_boundaries) - 1):
   726|            y1 = h_boundaries[i]
   727|            y2 = h_boundaries[i + 1]
   728|            x1 = v_boundaries[j]
   729|            x2 = v_boundaries[j + 1]
   730|            
   731|            w = x2 - x1
   732|            h = y2 - y1
   733|            
   734|            if w < 50 or h < 50:
   735|                continue
   736|            
   737|            if img is not None:
   738|                region = img[y1:y2, x1:x2]
   739|                if is_black_region(region, threshold=30, white_ratio_threshold=min_white_ratio):
   740|                    continue
   741|            
   742|            regions.append((x1, y1, w, h))
   743|    
   744|    return regions
   745|
   746|
   747|def is_black_region(region, threshold=30, white_ratio_threshold=0.1):
   748|    """检查区域是否是黑色/无效区域"""
   749|    import cv2
   750|    import numpy as np
   751|    
   752|    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
   753|    
   754|    white_pixels = np.sum(gray > 200)
   755|    total_pixels = gray.size
   756|    white_ratio = white_pixels / total_pixels
   757|    
   758|    mean_brightness = np.mean(gray)
   759|    
   760|    if white_ratio < white_ratio_threshold or mean_brightness < threshold:
   761|        return True
   762|    
   763|    return False
   764|
   765|
   766|def auto_detect_grid(binary, width, height, img=None):
   767|    """自动检测网格"""
   768|    import numpy as np
   769|    
   770|    h_proj = np.sum(binary, axis=1)
   771|    v_proj = np.sum(binary, axis=0)
   772|    
   773|    h_splits = find_splits_from_projection(h_proj, threshold=np.max(h_proj)*0.1, min_gap=50)
   774|    v_splits = find_splits_from_projection(v_proj, threshold=np.max(v_proj)*0.1, min_gap=50)
   775|    
   776|    h_boundaries = [0] + h_splits + [height]
   777|    v_boundaries = [0] + v_splits + [width]
   778|    
   779|    regions = []
   780|    for i in range(len(h_boundaries) - 1):
   781|        for j in range(len(v_boundaries) - 1):
   782|            y1 = h_boundaries[i]
   783|            y2 = h_boundaries[i + 1]
   784|            x1 = v_boundaries[j]
   785|            x2 = v_boundaries[j + 1]
   786|            
   787|            w = x2 - x1
   788|            h = y2 - y1
   789|            
   790|            if w < 50 or h < 50:
   791|                continue
   792|            
   793|            if img is not None:
   794|                region = img[y1:y2, x1:x2]
   795|                if is_black_region(region, threshold=30, white_ratio_threshold=0.1):
   796|                    continue
   797|            
   798|            regions.append((x1, y1, w, h))
   799|    
   800|    return regions
   801|
   802|
   803|def find_splits_from_projection(projection, threshold, min_gap=50):
   804|    """从投影中找到分割位置"""
   805|    splits = []
   806|    below_threshold = False
   807|    start = 0
   808|    
   809|    for i, val in enumerate(projection):
   810|        if val < threshold and not below_threshold:
   811|            below_threshold = True
   812|            start = i
   813|        elif val >= threshold and below_threshold:
   814|            below_threshold = False
   815|            mid = (start + i) // 2
   816|            if i - start >= 10:
   817|                splits.append(mid)
   818|    
   819|    return merge_nearby_lines(splits, gap=min_gap)
   820|
   821|
   822|def crop_black_edges(image, threshold=30, margin=2):
   823|    """裁剪图片的黑色边缘和红色线条"""
   824|    import cv2
   825|    import numpy as np
   826|    
   827|    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
   828|    
   829|    lower_red1 = np.array([0, 50, 50])
   830|    upper_red1 = np.array([10, 255, 255])
   831|    mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
   832|    
   833|    lower_red2 = np.array([160, 50, 50])
   834|    upper_red2 = np.array([180, 255, 255])
   835|    mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
   836|    
   837|    mask_red = mask_red1 | mask_red2
   838|    
   839|    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
   840|    mask_black = gray > threshold
   841|    
   842|    mask_valid = mask_black & (mask_red == 0)
   843|    
   844|    rows = np.any(mask_valid, axis=1)
   845|    cols = np.any(mask_valid, axis=0)
   846|    
   847|    if not np.any(rows) or not np.any(cols):
   848|        return image
   849|    
   850|    rmin, rmax = np.where(rows)[0][[0, -1]]
   851|    cmin, cmax = np.where(cols)[0][[0, -1]]
   852|    
   853|    rmin = max(0, rmin - margin)
   854|    rmax = min(image.shape[0] - 1, rmax + margin)
   855|    cmin = max(0, cmin - margin)
   856|    cmax = min(image.shape[1] - 1, cmax + margin)
   857|    
   858|    return image[rmin:rmax+1, cmin:cmax+1]
   859|
