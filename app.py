#!/usr/bin/env python3
"""
Arapça PDF Temizleyici - Masaüstü Uygulaması
Flet framework ile cross-platform GUI
"""

import flet as ft
from pathlib import Path
import threading
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_processor import process_pdf
from image_cleaner import analyze_image


def main(page: ft.Page):
    # Page settings - show immediately
    page.title = "PDF Temizleyici"
    page.window.width = 550
    page.window.height = 700
    page.window.resizable = True
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.padding = 20
    
    # Show loading immediately
    loading = ft.Column(
        [
            ft.ProgressRing(width=50, height=50),
            ft.Text("Yükleniyor...", size=16)
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        expand=True
    )
    page.add(loading)
    page.update()
    
    # State
    selected_file = {"path": None}
    is_processing = {"value": False}
    
    # File picker
    def pick_file_result(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            filepath = e.files[0].path
            selected_file["path"] = filepath
            input_field.value = filepath
            
            # Auto-generate output path
            input_p = Path(filepath)
            output_p = input_p.parent / "output" / f"temizlenmis_{input_p.name}"
            output_field.value = str(output_p)
            page.update()
    
    file_picker = ft.FilePicker(on_result=pick_file_result)
    page.overlay.append(file_picker)
    
    # Save file picker
    def save_file_result(e: ft.FilePickerResultEvent):
        if e.path:
            output_field.value = e.path
            page.update()
    
    save_picker = ft.FilePicker(on_result=save_file_result)
    page.overlay.append(save_picker)
    
    # Progress update
    def update_progress(current, total):
        progress = current / total
        progress_bar.value = progress
        status_text.value = f"İşleniyor: {current}/{total} sayfa"
        page.update()
    
    # Process PDF
    def process_thread():
        try:
            input_path = selected_file["path"]
            output_path = output_field.value
            dpi = int(dpi_dropdown.value)
            center = center_switch.value
            
            # Create output directory
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            total, edited, pages = process_pdf(
                input_path,
                output_path,
                analyze_image,
                dpi=dpi,
                progress_callback=update_progress,
                center_content=center
            )
            
            # Success
            progress_bar.value = 1
            status_text.value = f"✓ Tamamlandı! {edited}/{total} sayfa düzenlendi"
            status_text.color = ft.Colors.GREEN
            
            # Show dialog
            page.open(
                ft.AlertDialog(
                    title=ft.Text("✅ Tamamlandı!"),
                    content=ft.Text(
                        f"PDF başarıyla temizlendi!\n\n"
                        f"Toplam sayfa: {total}\n"
                        f"Düzenlenen: {edited}\n\n"
                        f"Çıktı: {output_path}"
                    )
                )
            )
            
        except Exception as e:
            status_text.value = f"❌ Hata: {str(e)}"
            status_text.color = ft.Colors.RED
        
        finally:
            is_processing["value"] = False
            process_btn.disabled = False
            process_btn.text = "🚀 TEMİZLE"
            page.update()
    
    def start_processing(e):
        if is_processing["value"]:
            return
        
        if not selected_file["path"]:
            page.open(ft.SnackBar(ft.Text("Lütfen bir PDF dosyası seçin!"), bgcolor=ft.Colors.RED))
            return
        
        if not output_field.value:
            page.open(ft.SnackBar(ft.Text("Lütfen çıktı yolunu belirleyin!"), bgcolor=ft.Colors.RED))
            return
        
        if not Path(selected_file["path"]).exists():
            page.open(ft.SnackBar(ft.Text("Seçilen dosya bulunamadı!"), bgcolor=ft.Colors.RED))
            return
        
        is_processing["value"] = True
        process_btn.disabled = True
        process_btn.text = "İşleniyor..."
        progress_bar.value = 0
        status_text.value = "Başlatılıyor..."
        status_text.color = None
        page.update()
        
        thread = threading.Thread(target=process_thread, daemon=True)
        thread.start()
    
    # === UI Components ===
    
    # Title
    title = ft.Text(
        "🧹 Arapça PDF Temizleyici",
        size=28,
        weight=ft.FontWeight.BOLD,
        text_align=ft.TextAlign.CENTER
    )
    
    # File input field
    input_field = ft.TextField(
        label="📄 PDF Dosya Yolu",
        hint_text="Dosya yolunu yapıştırın veya Seç butonuna tıklayın",
        expand=True,
        on_change=lambda e: update_input(e.control.value)
    )
    
    def update_input(path):
        if path:
            selected_file["path"] = path
            # Auto-generate output path
            input_p = Path(path)
            if input_p.exists():
                output_p = input_p.parent / "output" / f"temizlenmis_{input_p.name}"
                output_field.value = str(output_p)
                page.update()
    
    select_btn = ft.ElevatedButton(
        "📁 Seç",
        icon=ft.Icons.FOLDER_OPEN,
        on_click=lambda _: file_picker.pick_files(
            allowed_extensions=["pdf"],
            dialog_title="PDF Dosyası Seç"
        )
    )
    
    input_row = ft.Row([input_field, select_btn], spacing=10)
    
    file_card = ft.Card(
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.PICTURE_AS_PDF, size=40, color=ft.Colors.BLUE),
                    ft.Text("PDF dosyasını seçin veya yolu yapıştırın", size=14),
                    input_row,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15
            ),
            padding=20,
        )
    )
    
    # Settings
    dpi_dropdown = ft.Dropdown(
        label="Çözünürlük (DPI)",
        value="200",
        options=[
            ft.dropdown.Option("150", "150 - Hızlı"),
            ft.dropdown.Option("200", "200 - Normal"),
            ft.dropdown.Option("300", "300 - Yüksek Kalite")
        ],
        width=200
    )
    
    center_switch = ft.Switch(label="İçeriği sayfada ortala", value=True)
    debug_switch = ft.Switch(label="Debug görüntüleri (ilk 10 sayfa)", value=False)
    
    settings_card = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text("⚙️ Ayarlar", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(height=10),
                dpi_dropdown,
                center_switch,
                debug_switch
            ], spacing=10),
            padding=20
        )
    )
    
    # Output path
    output_field = ft.TextField(
        label="📁 Çıktı dosyası",
        hint_text="output/temizlenmis_dosya.pdf",
        expand=True
    )
    
    output_btn = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN,
        on_click=lambda _: save_picker.save_file(
            file_name="temizlenmis.pdf",
            allowed_extensions=["pdf"],
            dialog_title="Çıktı Dosyası Seç"
        )
    )
    
    output_row = ft.Row([output_field, output_btn])
    
    # Progress
    progress_bar = ft.ProgressBar(value=0, width=500)
    status_text = ft.Text("Hazır", size=12)
    
    # Process button
    process_btn = ft.ElevatedButton(
        "🚀 TEMİZLE",
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.GREEN_700,
            color=ft.Colors.WHITE,
            padding=20
        ),
        width=500,
        height=60,
        on_click=start_processing
    )
    
    # Info
    info_text = ft.Text(
        "Taranmış Arapça PDF'lerdeki lekeleri ve çizgileri temizler.\nYazı ve görseller korunur.",
        size=12,
        color=ft.Colors.GREY,
        text_align=ft.TextAlign.CENTER
    )
    
    # Clear loading and show main UI
    page.clean()
    
    # Layout
    page.add(
        ft.Column(
            [
                title,
                ft.Container(height=10),
                file_card,
                ft.Container(height=10),
                settings_card,
                ft.Container(height=10),
                output_row,
                ft.Container(height=15),
                progress_bar,
                status_text,
                ft.Container(height=10),
                process_btn,
                ft.Container(height=10),
                info_text
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
    )


if __name__ == "__main__":
    ft.app(target=main)
