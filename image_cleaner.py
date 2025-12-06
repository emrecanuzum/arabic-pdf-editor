"""
Görüntü temizleme modülü.
Metin bloklarını bul (lekeler hariç), içerik dışını temizle.
"""

import cv2
import numpy as np
from typing import Tuple, List


def is_text_block(roi_gray: np.ndarray, min_line_count: int = 2) -> bool:
    """
    Bir bölgenin gerçek metin bloğu olup olmadığını kontrol eder.
    Metin blokları yatay satırlar içerir, lekeler içermez.
    """
    if roi_gray.size == 0:
        return False
    
    height, width = roi_gray.shape
    
    # Çok küçük alanlar metin olamaz
    if height < 20 or width < 50:
        return False
    
    # Binary
    _, binary = cv2.threshold(roi_gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # Yatay projeksiyon - her satırdaki koyu piksel sayısı
    h_proj = np.sum(binary, axis=1) / 255
    
    # Satırları bul (projeksiyon eşiğini geçen satırlar)
    threshold = width * 0.1  # Genişliğin %10'u kadar koyu piksel
    text_rows = h_proj > threshold
    
    # Ardışık metin satırlarını say
    line_count = 0
    in_line = False
    for is_text in text_rows:
        if is_text and not in_line:
            line_count += 1
            in_line = True
        elif not is_text:
            in_line = False
    
    # En az min_line_count satır olmalı
    return line_count >= min_line_count


def find_text_content_bounds(image: np.ndarray) -> Tuple[int, int, int, int]:
    """
    Sayfadaki gerçek metin içeriğinin sınırlarını bulur.
    Lekeler dahil edilmez.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    height, width = gray.shape
    
    # Binary
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # Metin satırları oluştur
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
    lines = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_h)
    
    # Paragraflar
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 10))
    blocks = cv2.morphologyEx(lines, cv2.MORPH_CLOSE, kernel_v)
    
    # Genişlet
    kernel_expand = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 8))
    blocks = cv2.dilate(blocks, kernel_expand, iterations=1)
    
    contours, _ = cv2.findContours(blocks, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    valid_boxes = []
    
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        
        # Minimum alan (lekeler genellikle küçük)
        if area < 2000:
            continue
        
        # Minimum boyutlar
        if w < 50 or h < 20:
            continue
        
        # Aspect ratio kontrolü
        aspect = w / h
        if aspect > 30 or aspect < 0.1:  # Çok ince çizgi
            continue
        
        # Gerçek metin bloğu mu kontrol et
        roi = gray[y:y+h, x:x+w]
        if not is_text_block(roi, min_line_count=1):
            continue
        
        valid_boxes.append((x, y, x + w, y + h))
    
    if not valid_boxes:
        # Fallback - güvenli sınırlar
        return (50, 50, width - 50, height - 50)
    
    # Tüm geçerli kutuların sınırları
    min_x = min(box[0] for box in valid_boxes)
    min_y = min(box[1] for box in valid_boxes)
    max_x = max(box[2] for box in valid_boxes)
    max_y = max(box[3] for box in valid_boxes)
    
    # Padding
    padding = 8
    return (
        max(0, min_x - padding),
        max(0, min_y - padding),
        min(width, max_x + padding),
        min(height, max_y + padding)
    )


def find_areas_to_clean(image: np.ndarray) -> Tuple[List[Tuple[int, int, int, int]], bool]:
    """
    Temizlenecek alanları bulur.
    İçerik sınırları dışındaki kenarlar temizlenecek.
    """
    height, width = image.shape[:2]
    
    # İçerik sınırlarını bul
    x0, y0, x1, y1 = find_text_content_bounds(image)
    
    # Kenar dikdörtgenleri
    rects = []
    
    # Üst kenar
    if y0 > 5:
        rects.append((0, 0, width, y0))
    
    # Alt kenar
    if y1 < height - 5:
        rects.append((0, y1, width, height))
    
    # Sol kenar
    if x0 > 5:
        rects.append((0, y0, x0, y1))
    
    # Sağ kenar
    if x1 < width - 5:
        rects.append((x1, y0, width, y1))
    
    return rects, len(rects) > 0


def analyze_image(image: np.ndarray) -> Tuple[List[Tuple[int, int, int, int]], bool]:
    """
    Görüntüyü analiz eder.
    """
    return find_areas_to_clean(image)
