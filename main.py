#!/usr/bin/env python3
"""
Arapça PDF Temizleyici
Taranmış PDF'lerdeki lekeleri ve artifaktları temizler.
Yazı ve görsel alanlarına dokunmaz.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
import fitz
import cv2
import numpy as np
from PIL import Image
import io

from pdf_processor import process_pdf
from image_cleaner import analyze_image, find_text_content_bounds


def print_banner():
    """Program başlığını yazdırır."""
    print("""
╔═══════════════════════════════════════════════════════════╗
║            ARAPÇA PDF TEMİZLEYİCİ v1.0                   ║
║         Taranmış Sayfalardaki Lekeleri Temizler          ║
╚═══════════════════════════════════════════════════════════╝
""")


def print_progress(current: int, total: int):
    """İlerleme durumunu yazdırır."""
    percent = (current / total) * 100
    bar_length = 40
    filled = int(bar_length * current / total)
    bar = '█' * filled + '░' * (bar_length - filled)
    print(f'\r  İşleniyor: [{bar}] {current}/{total} (%{percent:.1f})', end='', flush=True)


def print_report(total: int, edited_count: int, edited_pages: list, output_path: str, elapsed: float, debug_dir: str = None):
    """Sonuç raporunu yazdırır."""
    print("\n")
    print("═" * 60)
    print("                    TEMİZLEME RAPORU")
    print("═" * 60)
    print(f"  Toplam sayfa sayısı    : {total}")
    print(f"  Düzenlenen sayfa sayısı: {edited_count}")
    
    if total > 0:
        ratio = (edited_count / total) * 100
        print(f"  Düzenleme oranı        : %{ratio:.1f}")
    
    print(f"  İşlem süresi           : {elapsed:.1f} saniye")
    print()
    
    if edited_pages:
        pages_str = ", ".join(map(str, edited_pages[:20]))
        if len(edited_pages) > 20:
            pages_str += f" ... (+{len(edited_pages) - 20} sayfa daha)"
        print(f"  Düzenlenen sayfalar    : {pages_str}")
    else:
        print("  Düzenlenen sayfalar    : Yok (Hiçbir sayfada artifakt bulunamadı)")
    
    print()
    print(f"  Çıktı dosyası          : {output_path}")
    
    if debug_dir:
        print(f"  Debug görüntüleri      : {debug_dir}")
    
    print("═" * 60)


def page_to_image(page, dpi=200):
    """PDF sayfasını numpy array'e çevirir."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("ppm")
    img = Image.open(io.BytesIO(img_data))
    return np.array(img)


def generate_debug_images(input_path: str, debug_dir: Path, dpi: int = 200, max_pages: int = 10):
    """İlk N sayfa için debug görüntüleri oluşturur."""
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open(input_path)
    num_pages = min(len(doc), max_pages)
    
    print(f"\n  Debug görüntüleri oluşturuluyor (ilk {num_pages} sayfa)...")
    
    for page_num in range(num_pages):
        page = doc[page_num]
        image = page_to_image(page, dpi)
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        height, width = image.shape[:2]
        
        # İçerik sınırlarını bul
        bounds = find_text_content_bounds(image)
        x0, y0, x1, y1 = bounds
        
        # Temizlenecek alanları bul
        rects, _ = analyze_image(image)
        
        # --- 1. Orijinal + İçerik Sınırları ---
        vis_bounds = image_bgr.copy()
        # Yeşil kutu = korunan içerik
        cv2.rectangle(vis_bounds, (x0, y0), (x1, y1), (0, 255, 0), 3)
        # Label
        cv2.putText(vis_bounds, "Korunan Alan", (x0 + 10, y0 + 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # --- 2. Temizlenecek alanlar (kırmızı) ---
        for (rx0, ry0, rx1, ry1) in rects:
            cv2.rectangle(vis_bounds, (int(rx0), int(ry0)), (int(rx1), int(ry1)), (0, 0, 255), -1)
        
        # Kaydet
        output_file = debug_dir / f"sayfa_{page_num + 1:03d}_analiz.png"
        cv2.imwrite(str(output_file), vis_bounds)
        
        # --- 3. Temizlenmiş simülasyon ---
        cleaned = image_bgr.copy()
        for (rx0, ry0, rx1, ry1) in rects:
            cleaned[int(ry0):int(ry1), int(rx0):int(rx1)] = [255, 255, 255]
        
        output_file2 = debug_dir / f"sayfa_{page_num + 1:03d}_temiz.png"
        cv2.imwrite(str(output_file2), cleaned)
        
        print(f"\r    Sayfa {page_num + 1}/{num_pages} işlendi", end='', flush=True)
    
    doc.close()
    print(f"\n  {num_pages * 2} debug görüntüsü oluşturuldu.")


def main():
    parser = argparse.ArgumentParser(
        description='Taranmış Arapça PDF dosyalarındaki lekeleri temizler.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnek kullanım:
  python main.py kitap.pdf
  python main.py kitap.pdf -o temiz_kitap.pdf
  python main.py kitap.pdf --dpi 300
  python main.py kitap.pdf --debug
        """
    )
    
    parser.add_argument('input', help='Temizlenecek PDF dosyası')
    parser.add_argument('-o', '--output', help='Çıktı dosyası (varsayılan: temizlenmis_[girdi].pdf)')
    parser.add_argument('--dpi', type=int, default=200, help='İşleme çözünürlüğü (varsayılan: 200)')
    parser.add_argument('--debug', action='store_true', help='İlk 10 sayfa için debug görüntüleri oluştur')
    parser.add_argument('--debug-pages', type=int, default=10, help='Debug için kaç sayfa (varsayılan: 10)')
    
    args = parser.parse_args()
    
    # Validate input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"HATA: Dosya bulunamadı: {input_path}")
        sys.exit(1)
    
    if not input_path.suffix.lower() == '.pdf':
        print(f"HATA: Sadece PDF dosyaları desteklenir: {input_path}")
        sys.exit(1)
    
    # Set output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = input_path.parent / "output"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"temizlenmis_{input_path.name}"
    
    # Debug directory
    debug_dir = input_path.parent / "debug_output" / input_path.stem
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print_banner()
    print(f"  Girdi  : {input_path}")
    print(f"  Çıktı  : {output_path}")
    print(f"  DPI    : {args.dpi}")
    if args.debug:
        print(f"  Debug  : İlk {args.debug_pages} sayfa")
    print()
    
    # Generate debug images if requested
    if args.debug:
        generate_debug_images(str(input_path), debug_dir, args.dpi, args.debug_pages)
    
    # Process
    start_time = datetime.now()
    
    try:
        total, edited_count, edited_pages = process_pdf(
            str(input_path),
            str(output_path),
            analyze_image,
            dpi=args.dpi,
            progress_callback=print_progress
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print_report(total, edited_count, edited_pages, str(output_path), elapsed, 
                    str(debug_dir) if args.debug else None)
        
    except Exception as e:
        print(f"\nHATA: PDF işlenirken bir sorun oluştu: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
