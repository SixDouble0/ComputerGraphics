from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from . import filters, image_io, operations
from .image_buffer import ImageBuffer


class ImageApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Projekt 4 - Przekształcenia obrazów")
        self.geometry("1200x800")

        self.current_image: ImageBuffer | None = None
        self.display_image: Image.Image | None = None
        self.photo_image: ImageTk.PhotoImage | None = None
        self.canvas_image_id: int | None = None

        self.zoom_var = tk.DoubleVar(value=1.0)
        self.status_var = tk.StringVar(value="Brak załadowanego obrazu")
        self._suppress_zoom_callback = False
        self._user_zoom_override = False

        self._build_ui()

    def _build_ui(self) -> None:
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Otwórz...", command=self.open_image)
        file_menu.add_command(label="Zapisz jako JPEG...", command=self.save_as_jpeg)
        file_menu.add_command(label="Zapisz jako PPM (ASCII)...", command=lambda: self.save_as_ppm(binary=False))
        file_menu.add_command(label="Zapisz jako PPM (Binarny)...", command=lambda: self.save_as_ppm(binary=True))
        file_menu.add_separator()
        file_menu.add_command(label="Wyjście", command=self.destroy)
        menubar.add_cascade(label="Plik", menu=file_menu)

        point_menu = tk.Menu(menubar, tearoff=0)
        point_menu.add_command(label="Dodawanie", command=self.add_constant)
        point_menu.add_command(label="Odejmowanie", command=self.subtract_constant)
        point_menu.add_command(label="Mnożenie", command=self.multiply_constant)
        point_menu.add_command(label="Dzielenie", command=self.divide_constant)
        point_menu.add_command(label="Zmiana jasności", command=self.change_brightness)
        point_menu.add_separator()
        point_menu.add_command(label="Skala szarości (średnia)", command=self.grayscale_average)
        point_menu.add_command(label="Skala szarości (luminancja)", command=self.grayscale_luminance)
        point_menu.add_command(label="Skalowanie liniowe RGB", command=self.linear_scale)
        menubar.add_cascade(label="Przekształcenia punktowe", menu=point_menu)

        filter_menu = tk.Menu(menubar, tearoff=0)
        filter_menu.add_command(label="Filtr uśredniający", command=self.apply_mean_filter)
        filter_menu.add_command(label="Filtr medianowy", command=self.apply_median_filter)
        filter_menu.add_command(label="Sobel (krawędzie)", command=self.apply_sobel)
        filter_menu.add_command(label="Filtr wyostrzający", command=self.apply_sharpen)
        filter_menu.add_command(label="Rozmycie Gaussa", command=self.apply_gaussian)
        filter_menu.add_command(label="Dowolna maska", command=self.apply_custom_kernel)
        menubar.add_cascade(label="Filtry", menu=filter_menu)

        self.config(menu=menubar)

        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=10, pady=5)
        ttk.Label(controls, text="Powiększenie (1x - 16x):").pack(side="left")
        zoom_slider = ttk.Scale(
            controls,
            from_=1.0,
            to=16.0,
            variable=self.zoom_var,
            command=self._on_zoom_slider,
        )
        zoom_slider.pack(side="left", fill="x", expand=True, padx=10)

        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(canvas_frame, background="black", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        scrollbar_y = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        scrollbar_y.pack(side="right", fill="y")
        scrollbar_x = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        scrollbar_x.pack(fill="x")
        self.canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self.canvas.bind("<B1-Motion>", self._on_pan_move)
        self.canvas.bind("<Motion>", self._on_mouse_move)

        status_bar = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status_bar.pack(fill="x")

    def open_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz obraz",
            filetypes=[("Obrazy", "*.ppm;*.jpg;*.jpeg"), ("PPM", "*.ppm"), ("JPEG", "*.jpg;*.jpeg")],
        )
        if not path:
            return
        try:
            self.current_image = image_io.load_image(path)
            self.status_var.set(f"Wczytano: {Path(path).name} ({self.current_image.width}x{self.current_image.height})")
            self._fit_image_to_canvas(force=True)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Błąd", f"Nie udało się wczytać obrazu:\n{exc}")

    def save_as_jpeg(self) -> None:
        if not self.current_image:
            messagebox.showinfo("Informacja", "Brak obrazu do zapisania.")
            return
        path = filedialog.asksaveasfilename(
            title="Zapisz jako JPEG",
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg;*.jpeg")],
        )
        if not path:
            return
        quality = simpledialog.askinteger("Kompresja", "Podaj jakość (1-95):", minvalue=1, maxvalue=95, initialvalue=90)
        if quality is None:
            return
        try:
            image_io.save_as_jpeg(self.current_image, path, quality=quality)
            self.status_var.set(f"Zapisano JPEG (jakość {quality})")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Błąd", f"Nie udało się zapisać JPEG:\n{exc}")

    def save_as_ppm(self, binary: bool) -> None:
        if not self.current_image:
            messagebox.showinfo("Informacja", "Brak obrazu do zapisania.")
            return
        ext = ".ppm"
        path = filedialog.asksaveasfilename(title="Zapisz jako PPM", defaultextension=ext, filetypes=[("PPM", "*.ppm")])
        if not path:
            return
        try:
            image_io.save_as_ppm(self.current_image, path, binary=binary)
            fmt = "P6" if binary else "P3"
            self.status_var.set(f"Zapisano {fmt} -> {Path(path).name}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Błąd", f"Nie udało się zapisać PPM:\n{exc}")

    def add_constant(self) -> None:
        value = self._ask_float("Dodawanie", "Podaj wartość dodatnią/ujemną:")
        if value is None:
            return
        self._apply_operation(lambda img: operations.add_constant(img, value), f"Dodano {value}")

    def subtract_constant(self) -> None:
        value = self._ask_float("Odejmowanie", "Podaj wartość:")
        if value is None:
            return
        self._apply_operation(lambda img: operations.subtract_constant(img, value), f"Odjęto {value}")

    def multiply_constant(self) -> None:
        factor = self._ask_float("Mnożenie", "Podaj mnożnik (np. 1.2):")
        if factor is None:
            return
        self._apply_operation(lambda img: operations.multiply(img, factor), f"Pomnożono przez {factor}")

    def divide_constant(self) -> None:
        divisor = self._ask_float("Dzielenie", "Podaj dzielnik (nie 0):")
        if divisor in (None, 0):
            return
        self._apply_operation(lambda img: operations.divide(img, divisor), f"Podzielono przez {divisor}")

    def change_brightness(self) -> None:
        delta = self._ask_float("Zmiana jasności", "Podaj przyrost (np. 15 lub -20):")
        if delta is None:
            return
        self._apply_operation(lambda img: operations.change_brightness(img, delta), f"Jasność {delta:+}")

    def grayscale_average(self) -> None:
        self._apply_operation(operations.grayscale_average, "Skala szarości (średnia)")

    def grayscale_luminance(self) -> None:
        self._apply_operation(operations.grayscale_luminance, "Skala szarości (luminancja)")

    def linear_scale(self) -> None:
        r = self._ask_float("Skalowanie R", "Podaj skalę R (np. 1.0):")
        if r is None:
            return
        g = self._ask_float("Skalowanie G", "Podaj skalę G (np. 1.0):")
        if g is None:
            return
        b = self._ask_float("Skalowanie B", "Podaj skalę B (np. 1.0):")
        if b is None:
            return
        self._apply_operation(lambda img: operations.linear_color_scale(img, r, g, b), "Skalowanie liniowe RGB")

    def apply_mean_filter(self) -> None:
        size = self._ask_kernel_size()
        if size is None:
            return
        self._apply_operation(lambda img: filters.mean_filter(img, size=size), f"Filtr uśredniający {size}x{size}")

    def apply_median_filter(self) -> None:
        size = self._ask_kernel_size()
        if size is None:
            return
        self._apply_operation(lambda img: filters.median_filter(img, size=size), f"Filtr medianowy {size}x{size}")

    def apply_sobel(self) -> None:
        self._apply_operation(filters.sobel_edge, "Sobel")

    def apply_sharpen(self) -> None:
        self._apply_operation(filters.high_pass_sharpen, "Wyostrzanie")

    def apply_gaussian(self) -> None:
        sigma = self._ask_float("Rozmycie Gaussa", "Podaj sigma (np. 1.5):")
        if sigma is None:
            return
        self._apply_operation(lambda img: filters.gaussian_blur(img, sigma=sigma), f"Gauss sigma={sigma}")

    def apply_custom_kernel(self) -> None:
        size = self._ask_kernel_size()
        if size is None:
            return
        text = simpledialog.askstring(
            "Maska",
            "Podaj wartości maski (wiersze oddzielone enterem, wartości spacjami):",
        )
        if not text:
            return
        rows = [list(map(float, line.strip().split())) for line in text.strip().splitlines() if line.strip()]
        if len(rows) != size or any(len(row) != size for row in rows):
            messagebox.showerror("Błąd", "Liczba wartości nie zgadza się z rozmiarem maski.")
            return
        divisor = self._ask_float("Dzielnik", "Podaj dzielnik (opcjonalny, Enter = suma):", allow_empty=True)
        offset = self._ask_float("Offset", "Podaj offset (np. 0):", allow_empty=True)
        kwargs = {}
        if divisor is not None:
            kwargs["divisor"] = divisor
        if offset is not None:
            kwargs["offset"] = offset
        self._apply_operation(lambda img: filters.custom_convolution(img, rows, **kwargs), "Własna maska")

    def update_display_image(self) -> None:
        if not self.current_image:
            return
        pil_image = self.current_image.to_pillow_image()
        scale = max(1.0, self.zoom_var.get())
        target_size = (int(self.current_image.width * scale), int(self.current_image.height * scale))
        if target_size != (self.current_image.width, self.current_image.height):
            resample = Image.NEAREST if scale >= 1 else Image.BILINEAR
            pil_image = pil_image.resize(target_size, resample=resample)
        if scale >= 8.0:
            pil_image = self._add_pixel_overlay(pil_image, scale)
        self.display_image = pil_image
        self.photo_image = ImageTk.PhotoImage(pil_image)
        if self.canvas_image_id is None:
            self.canvas_image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.photo_image)
        else:
            self.canvas.itemconfig(self.canvas_image_id, image=self.photo_image)
        bbox = self.canvas.bbox(self.canvas_image_id)
        if bbox:
            self.canvas.configure(scrollregion=bbox)

    def _add_pixel_overlay(self, pil_image, scale: float):
        if not self.current_image:
            return pil_image
        draw = ImageDraw.Draw(pil_image)
        font = ImageFont.load_default()
        for y in range(self.current_image.height):
            for x in range(self.current_image.width):
                r, g, b = self.current_image.get_pixel(x, y)
                text = f"{r},{g},{b}"
                x0 = x * scale
                y0 = y * scale
                draw.rectangle((x0, y0, x0 + scale, y0 + scale), outline="gray")
                draw.text((x0 + 2, y0 + 2), text, fill="white", font=font)
        return pil_image

    def _apply_operation(self, op, label: str) -> None:
        if not self.current_image:
            messagebox.showinfo("Informacja", "Wczytaj najpierw obraz.")
            return
        try:
            self.current_image = op(self.current_image)
            self.status_var.set(label)
            self.update_display_image()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Błąd", f"Nie udało się zastosować operacji:\n{exc}")

    def _ask_float(self, title: str, prompt: str, allow_empty: bool = False):
        value = simpledialog.askstring(title, prompt)
        if value in (None, ""):
            return None if allow_empty else None
        try:
            return float(value)
        except ValueError:
            messagebox.showerror("Błąd", "Podano niepoprawną liczbę.")
            return None

    def _ask_kernel_size(self) -> int | None:
        size = simpledialog.askinteger("Rozmiar maski", "Podaj nieparzysty rozmiar (3,5,...):", minvalue=1, initialvalue=3)
        if size is None:
            return None
        if size % 2 == 0:
            messagebox.showerror("Błąd", "Rozmiar maski musi być nieparzysty.")
            return None
        return size

    def _on_pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _on_pan_move(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_mouse_move(self, event):
        if not self.current_image:
            return
        scale = max(1.0, self.zoom_var.get())
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        x = int(canvas_x / scale)
        y = int(canvas_y / scale)
        if 0 <= x < self.current_image.width and 0 <= y < self.current_image.height:
            r, g, b = self.current_image.get_pixel(x, y)
            self.status_var.set(f"X:{x} Y:{y} | R:{r} G:{g} B:{b}")
        else:
            self.status_var.set("Poza obrazem")

    def _fit_image_to_canvas(self, force: bool = False) -> None:
        if not self.current_image:
            return
        if not force and self._user_zoom_override:
            return
        canvas_width = max(1, self.canvas.winfo_width())
        canvas_height = max(1, self.canvas.winfo_height())
        if canvas_width <= 1 or canvas_height <= 1:
            self.after(50, lambda: self._fit_image_to_canvas(force))
            return
        scale_x = canvas_width / self.current_image.width
        scale_y = canvas_height / self.current_image.height
        scale = min(scale_x, scale_y)
        scale = max(1.0, min(16.0, scale))
        if abs(scale - self.zoom_var.get()) < 1e-3 and not force:
            return
        self._user_zoom_override = False
        self._suppress_zoom_callback = True
        self.zoom_var.set(scale)
        self._suppress_zoom_callback = False
        self.update_display_image()

    def _on_zoom_slider(self, _value: str) -> None:
        if self._suppress_zoom_callback:
            return
        self._user_zoom_override = True
        self.update_display_image()

    def _on_canvas_resize(self, _event) -> None:
        if self.current_image:
            self._fit_image_to_canvas()


def run_app() -> None:
    app = ImageApp()
    app.mainloop()

