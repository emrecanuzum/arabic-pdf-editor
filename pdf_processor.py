"""
PDF işleme modülü.
Sayfaları temizler ve içeriği ortalar.
"""

import fitz  # PyMuPDF
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Tuple, Callable, Optional
import io


def page_to_image(page: fitz.Page, dpi: int = 200) -> np.ndarray:
    """PDF sayfasını numpy array'e çevirir."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("ppm")
    img = Image.open(io.BytesIO(img_data))
    return np.array(img)


def apply_white_rects(page: fitz.Page, rects: List[Tuple[float, float, float, float]]):
    """Sayfaya beyaz dikdörtgenler çizer."""
    for rect in rects:
        r = fitz.Rect(rect)
        shape = page.new_shape()
        shape.draw_rect(r)
        shape.finish(color=(1, 1, 1), fill=(1, 1, 1))
        shape.commit()


def center_page_content(
    doc: fitz.Document,
    page_num: int,
    content_bounds: Tuple[int, int, int, int],
    dpi: int = 200
):
    """
    Sayfa içeriğini ortalar.
    content_bounds: (x0, y0, x1, y1) görüntü koordinatlarında içerik sınırları
    """
    page = doc[page_num]
    page_rect = page.rect
    page_width = page_rect.width
    page_height = page_rect.height
    
    scale = dpi / 72
    
    # İçerik sınırlarını sayfa koordinatlarına çevir
    cx0, cy0, cx1, cy1 = content_bounds
    content_x0 = cx0 / scale
    content_y0 = cy0 / scale
    content_x1 = cx1 / scale
    content_y1 = cy1 / scale
    
    content_width = content_x1 - content_x0
    content_height = content_y1 - content_y0
    
    # Mevcut içerik merkezi
    current_center_x = (content_x0 + content_x1) / 2
    current_center_y = (content_y0 + content_y1) / 2
    
    # Sayfa merkezi
    page_center_x = page_width / 2
    page_center_y = page_height / 2
    
    # Kaydırma miktarı
    shift_x = page_center_x - current_center_x
    shift_y = page_center_y - current_center_y
    
    # Eğer kaydırma çok küçükse (zaten ortada), atla
    if abs(shift_x) < 5 and abs(shift_y) < 5:
        return False
    
    # İçerik alanını kırp
    clip_rect = fitz.Rect(content_x0, content_y0, content_x1, content_y1)
    
    # İçerik bölgesinin pixmap'ini al
    content_pix = page.get_pixmap(clip=clip_rect, matrix=fitz.Matrix(2, 2))
    
    # Pixmap'i numpy array'e çevir ve arka planı beyazlat
    img_array = np.frombuffer(content_pix.samples, dtype=np.uint8).reshape(
        content_pix.height, content_pix.width, content_pix.n
    )
    img_array = img_array.copy()  # Yazılabilir kopya
    
    # Açık gri pikselleri beyaza çevir (threshold: 200'den büyük = beyaz yap)
    if content_pix.n >= 3:  # RGB veya RGBA
        gray_mask = np.all(img_array[:, :, :3] > 200, axis=2)
        img_array[gray_mask] = 255
    
    # Numpy array'i tekrar PNG'ye çevir
    from PIL import Image as PILImage
    if content_pix.n == 4:  # RGBA
        pil_img = PILImage.fromarray(img_array, mode='RGBA')
    else:  # RGB
        pil_img = PILImage.fromarray(img_array, mode='RGB')
    
    import io
    img_buffer = io.BytesIO()
    pil_img.save(img_buffer, format='PNG')
    img_data = img_buffer.getvalue()
    
    # Sayfayı beyazla doldur
    shape = page.new_shape()
    shape.draw_rect(page_rect)
    shape.finish(color=(1, 1, 1), fill=(1, 1, 1))
    shape.commit()
    
    # Yeni konum hesapla (ortalanmış)
    new_x0 = (page_width - content_width) / 2
    new_y0 = (page_height - content_height) / 2
    new_rect = fitz.Rect(new_x0, new_y0, new_x0 + content_width, new_y0 + content_height)
    
    # İçeriği yeni konuma yerleştir
    page.insert_image(new_rect, stream=img_data)
    
    return True


def process_pdf(
    input_path: str, 
    output_path: str,
    analyze_func: Callable,
    dpi: int = 200,
    progress_callback: Optional[Callable] = None,
    center_content: bool = True
) -> Tuple[int, int, List[int]]:
    """
    PDF'i işler - kenarları temizler ve içeriği ortalar.
    
    Args:
        input_path: Girdi PDF yolu
        output_path: Çıktı PDF yolu
        analyze_func: Görüntü analiz fonksiyonu
        dpi: İşleme çözünürlüğü
        progress_callback: İlerleme callback'i
        center_content: İçeriği ortala
    
    Returns: (total_pages, edited_count, edited_page_numbers)
    """
    # Import here to avoid circular import
    from image_cleaner import find_text_content_bounds
    
    doc = fitz.open(input_path)
    total_pages = len(doc)
    edited_pages = []
    
    for page_num in range(total_pages):
        page = doc[page_num]
        
        # Sayfayı görüntüye çevir
        image = page_to_image(page, dpi)
        
        # Analiz et
        areas_to_clean, was_modified = analyze_func(image)
        
        if was_modified and areas_to_clean:
            edited_pages.append(page_num + 1)
            
            # Koordinatları çevir ve beyaz dikdörtgenler çiz
            scale = dpi / 72
            page_rects = []
            
            for (x0, y0, x1, y1) in areas_to_clean:
                page_rects.append((x0/scale, y0/scale, x1/scale, y1/scale))
            
            apply_white_rects(page, page_rects)
            
            # İçeriği ortala
            if center_content:
                content_bounds = find_text_content_bounds(image)
                center_page_content(doc, page_num, content_bounds, dpi)
        
        if progress_callback:
            progress_callback(page_num + 1, total_pages)
    
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    
    return total_pages, len(edited_pages), edited_pages
