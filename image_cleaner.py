"""
Görüntü temizleme modülü.
Metin bloklarını bul (lekeler hariç), içerik dışını temizle.
Arapça OCR ile sayfa numaralarını koru.
"""

import cv2
import numpy as np
import os
import sys
from typing import Tuple, List
from PIL import Image


def get_tesseract_path():
    """Bundle edilmiş veya sistem Tesseract yolunu döndürür."""
    # PyInstaller ile paketlenmişse
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Bundle edilmiş Tesseract'ı ara
    if sys.platform == 'win32':
        bundled_tesseract = os.path.join(base_path, 'tesseract_bundle', 'tesseract.exe')
        bundled_tessdata = os.path.join(base_path, 'tesseract_bundle', 'tessdata')
    else:  # macOS/Linux
        bundled_tesseract = os.path.join(base_path, 'tesseract_bundle', 'tesseract')
        bundled_tessdata = os.path.join(base_path, 'tesseract_bundle', 'tessdata')
    
    if os.path.exists(bundled_tesseract):
        # TESSDATA_PREFIX ayarla
        os.environ['TESSDATA_PREFIX'] = bundled_tessdata
        return bundled_tesseract
    
    return None  # Sistem Tesseract'ını kullan


# OCR için pytesseract
OCR_AVAILABLE = False
try:
    import pytesseract
    
    # Bundle edilmiş Tesseract varsa onu kullan
    tesseract_path = get_tesseract_path()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    
    # Test et
    pytesseract.get_tesseract_version()
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False


def has_arabic_or_number(image_region: np.ndarray) -> bool:
    """
    Bir görüntü bölgesinde Arapça metin veya sayı olup olmadığını OCR ile kontrol eder.
    """
    if not OCR_AVAILABLE:
        return True  # OCR yoksa varsayılan olarak koru
    
    try:
        # BGR -> RGB -> PIL Image
        if len(image_region.shape) == 3:
            rgb = cv2.cvtColor(image_region, cv2.COLOR_BGR2RGB)
        else:
            rgb = cv2.cvtColor(image_region, cv2.COLOR_GRAY2RGB)
        
        pil_img = Image.fromarray(rgb)
        
        # Arapça OCR çalıştır (sayılar için snum de ekle)
        text = pytesseract.image_to_string(pil_img, lang='ara+eng', config='--psm 6')
        
        # Temizle
        text = text.strip()
        
        # Boş değilse metin var demektir
        if len(text) > 0:
            # Sadece noktalama veya boşluk değilse
            cleaned = ''.join(c for c in text if c.isalnum())
            return len(cleaned) > 0
        
        return False
    except Exception:
        # OCR hatası olursa varsayılan olarak koru
        return True


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


def find_text_in_margin(image: np.ndarray, region: Tuple[int, int, int, int]) -> List[Tuple[int, int, int, int]]:
    """
    Kenar bölgesinde Arapça metin/sayı içeren alanları tespit eder.
    Sayfa numaraları ve küçük metin blokları için OCR kullanır.
    """
    rx0, ry0, rx1, ry1 = region
    
    # Bölge çok küçükse atla
    if rx1 - rx0 < 10 or ry1 - ry0 < 10:
        return []
    
    # Bölgeyi kes
    roi = image[ry0:ry1, rx0:rx1]
    if roi.size == 0:
        return []
    
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi.copy()
    
    # Binary (metin tespiti için)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # Küçük gürültüleri temizle
    kernel_clean = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_clean)
    
    # Metin karakterlerini birleştir
    kernel_connect = cv2.getStructuringElement(cv2.MORPH_RECT, (8, 4))
    connected = cv2.dilate(binary, kernel_connect, iterations=1)
    
    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    text_boxes = []
    
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        
        # Çok küçük veya çok büyük alanları atla
        if area < 100 or area > 50000:
            continue
        
        # Minimum boyut (sayfa numarası en az bu kadar olmalı)
        if w < 10 or h < 10:
            continue
        
        # Çok uzun çizgileri atla (leke olabilir)
        aspect = w / h if h > 0 else 0
        if aspect > 15 or aspect < 0.05:
            continue
        
        # Piksel yoğunluğu kontrolü (metin belirli bir yoğunlukta olmalı)
        roi_binary = binary[y:y+h, x:x+w]
        if roi_binary.size == 0:
            continue
        
        density = np.sum(roi_binary) / (255 * w * h)
        # Metin genellikle %5-60 yoğunlukta olur
        if density < 0.03 or density > 0.7:
            continue
        
        # OCR ile Arapça metin veya sayı kontrolü
        candidate_region = roi[y:y+h, x:x+w]
        if not has_arabic_or_number(candidate_region):
            continue  # OCR metin bulamadı, leke olabilir
        
        # Global koordinatlara çevir ve padding ekle
        padding = 5
        text_boxes.append((
            rx0 + max(0, x - padding),
            ry0 + max(0, y - padding),
            rx0 + min(rx1 - rx0, x + w + padding),
            ry0 + min(ry1 - ry0, y + h + padding)
        ))
    
    return text_boxes


def find_areas_to_clean(image: np.ndarray) -> Tuple[List[Tuple[int, int, int, int]], bool]:
    """
    Temizlenecek alanları bulur.
    İçerik sınırları dışındaki kenarlar temizlenecek.
    Dış alanlardaki metin/sayı blokları korunur.
    """
    height, width = image.shape[:2]
    
    # İçerik sınırlarını bul
    x0, y0, x1, y1 = find_text_content_bounds(image)
    
    # Kenar bölgelerini tanımla
    margin_regions = []
    
    # Üst kenar
    if y0 > 5:
        margin_regions.append(('top', (0, 0, width, y0)))
    
    # Alt kenar  
    if y1 < height - 5:
        margin_regions.append(('bottom', (0, y1, width, height)))
    
    # Sol kenar
    if x0 > 5:
        margin_regions.append(('left', (0, y0, x0, y1)))
    
    # Sağ kenar
    if x1 < width - 5:
        margin_regions.append(('right', (x1, y0, width, y1)))
    
    # Her kenar bölgesinde metin ara ve korunan alanları bul
    protected_boxes = []
    for name, region in margin_regions:
        text_boxes = find_text_in_margin(image, region)
        protected_boxes.extend(text_boxes)
    
    # Temizlenecek alanları hesapla (korunan alanlar hariç)
    rects_to_clean = []
    
    for name, (rx0, ry0, rx1, ry1) in margin_regions:
        # Bu bölgedeki korunan kutuları bul
        region_protected = [box for box in protected_boxes 
                           if box[0] >= rx0 and box[2] <= rx1 and 
                              box[1] >= ry0 and box[3] <= ry1]
        
        if not region_protected:
            # Korunan alan yok, tüm bölgeyi temizle
            rects_to_clean.append((rx0, ry0, rx1, ry1))
        else:
            # Korunan alanlar var, etrafını temizle
            # Basit yaklaşım: korunan alanları genişlet ve geri kalanı temizle
            # Daha karmaşık bir çözüm için bölgeyi parçalara ayırabiliriz
            
            if name == 'top' or name == 'bottom':
                # Yatay bölge - korunan alanların solunu ve sağını temizle
                for box in region_protected:
                    bx0, by0, bx1, by1 = box
                    # Korunan kutunun solundaki alan
                    if bx0 > rx0:
                        rects_to_clean.append((rx0, ry0, bx0, ry1))
                    # Korunan kutunun sağındaki alan
                    if bx1 < rx1:
                        rects_to_clean.append((bx1, ry0, rx1, ry1))
                    # Korunan kutunun üstü/altı (dikey olarak)
                    if by0 > ry0:
                        rects_to_clean.append((bx0, ry0, bx1, by0))
                    if by1 < ry1:
                        rects_to_clean.append((bx0, by1, bx1, ry1))
            else:
                # Dikey bölge - korunan alanların üstünü ve altını temizle
                for box in region_protected:
                    bx0, by0, bx1, by1 = box
                    # Üst
                    if by0 > ry0:
                        rects_to_clean.append((rx0, ry0, rx1, by0))
                    # Alt
                    if by1 < ry1:
                        rects_to_clean.append((rx0, by1, rx1, ry1))
                    # Sol/sağ
                    if bx0 > rx0:
                        rects_to_clean.append((rx0, by0, bx0, by1))
                    if bx1 < rx1:
                        rects_to_clean.append((bx1, by0, rx1, by1))
    
    return rects_to_clean, len(rects_to_clean) > 0


def analyze_image(image: np.ndarray) -> Tuple[List[Tuple[int, int, int, int]], bool]:
    """
    Görüntüyü analiz eder.
    """
    return find_areas_to_clean(image)
