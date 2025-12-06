#!/usr/bin/env python3
"""
Debug - sayfa analizi
"""

import fitz
import cv2
import numpy as np
from PIL import Image
import io
from pathlib import Path

from image_cleaner import find_text_content_bounds, find_areas_to_clean


def page_to_image(page, dpi=200):
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("ppm")
    img = Image.open(io.BytesIO(img_data))
    return np.array(img)


def main():
    pdf_path = "to-clean-example.pdf"
    output_dir = Path("debug_output")
    output_dir.mkdir(exist_ok=True)
    
    doc = fitz.open(pdf_path)
    
    # Sayfa 7 (0-indexed = 6)
    page_num = 6
    page = doc[page_num]
    image = page_to_image(page)
    
    print(f"=== Sayfa {page_num + 1} Debug ===")
    print(f"Görüntü boyutu: {image.shape}")
    
    image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    # Orijinal
    cv2.imwrite(str(output_dir / "1_original.png"), image_bgr)
    
    # İçerik sınırları
    bounds = find_text_content_bounds(image)
    print(f"İçerik sınırları: {bounds}")
    
    # Görselleştir
    vis = image_bgr.copy()
    x0, y0, x1, y1 = bounds
    cv2.rectangle(vis, (x0, y0), (x1, y1), (0, 255, 0), 3)
    cv2.imwrite(str(output_dir / "2_content_bounds.png"), vis)
    
    # Temizlenecek alanlar
    rects, was_modified = find_areas_to_clean(image)
    print(f"Temizlenecek alan: {len(rects)}")
    
    vis2 = image_bgr.copy()
    for (rx0, ry0, rx1, ry1) in rects:
        cv2.rectangle(vis2, (int(rx0), int(ry0)), (int(rx1), int(ry1)), (0, 0, 255), 2)
    cv2.imwrite(str(output_dir / "3_areas_to_clean.png"), vis2)
    
    # Temizlenmiş simülasyon
    cleaned = image_bgr.copy()
    for (rx0, ry0, rx1, ry1) in rects:
        cleaned[int(ry0):int(ry1), int(rx0):int(rx1)] = [255, 255, 255]
    cv2.imwrite(str(output_dir / "4_cleaned.png"), cleaned)
    
    doc.close()
    print(f"Debug: {output_dir}/")


if __name__ == "__main__":
    main()
