from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QImage, QPainter, QPen, QPixmap, QTransform
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from . import binarization, filters, histogram, image_io, operations
from .image_buffer import ImageBuffer


def _buffer_to_qimage(buffer: ImageBuffer) -> QImage:
    data = bytes(buffer.data)
    image = QImage(data, buffer.width, buffer.height, buffer.width * 3, QImage.Format.Format_RGB888)
    return image.copy()  # detach from temporary bytes


class ImageGraphicsView(QGraphicsView):
    zoomChanged = pyqtSignal(float)
    cursorMoved = pyqtSignal(int, int, object)  # object for tuple[int, int, int] | None

    def __init__(self) -> None:
        super().__init__()
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setMouseTracking(True)
        self.setBackgroundBrush(Qt.GlobalColor.black)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._buffer: ImageBuffer | None = None
        self._scale = 1.0
        self._overlay_threshold = 8.0
        self._auto_fit = True

    def set_image(self, pixmap: QPixmap, buffer: ImageBuffer) -> None:
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self._buffer = buffer
        self._scale = 1.0
        self._auto_fit = True
        self._apply_transform()

    def has_image(self) -> bool:
        return self._pixmap_item is not None

    def fit_image(self) -> None:
        if not self._pixmap_item:
            return
        view_rect = self.viewport().rect()
        if view_rect.width() == 0 or view_rect.height() == 0:
            return
        image_rect = self._pixmap_item.boundingRect()
        scale_x = view_rect.width() / image_rect.width()
        scale_y = view_rect.height() / image_rect.height()
        self._auto_fit = True
        self.set_scale(max(0.1, min(scale_x, scale_y)), user_initiated=False)

    def set_scale(self, scale: float, user_initiated: bool = False) -> None:
        scale = max(0.1, min(16.0, scale))
        if abs(scale - self._scale) < 1e-3:
            return
        self._scale = scale
        if user_initiated:
            self._auto_fit = False
        self._apply_transform()

    def current_scale(self) -> float:
        return self._scale

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if not self._pixmap_item:
            return
        angle = event.angleDelta().y()
        factor = 1.25 if angle > 0 else 0.8
        old_pos = self.mapToScene(event.position().toPoint())
        self.set_scale(self._scale * factor, user_initiated=True)
        self.centerOn(old_pos)
        self.zoomChanged.emit(self._scale)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        super().mouseMoveEvent(event)
        if not self._buffer or not self._pixmap_item:
            self.cursorMoved.emit(-1, -1, None)
            return
        scene_pos = self.mapToScene(event.position().toPoint())
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        if 0 <= x < self._buffer.width and 0 <= y < self._buffer.height:
            r, g, b = self._buffer.get_pixel(x, y)
            self.cursorMoved.emit(x, y, (r, g, b))
        else:
            self.cursorMoved.emit(-1, -1, None)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._pixmap_item and self._auto_fit:
            self.fit_image()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:  # type: ignore[override]
        super().drawForeground(painter, rect)
        if not self._buffer or self._scale < self._overlay_threshold or not self._pixmap_item:
            return
        painter.save()
        inv_scale = 1 / self._scale
        pix_rect = self._pixmap_item.boundingRect()
        visible = rect.intersected(pix_rect)
        start_x = max(0, int(visible.left() * inv_scale))
        end_x = min(self._buffer.width, int(visible.right() * inv_scale) + 1)
        start_y = max(0, int(visible.top() * inv_scale))
        end_y = min(self._buffer.height, int(visible.bottom() * inv_scale) + 1)
        font = QFont("Monospace", max(6, int(8 * inv_scale)))
        painter.setFont(font)
        pen = QPen(Qt.GlobalColor.gray)
        painter.setPen(pen)
        buffer = self._buffer
        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                r, g, b = buffer.get_pixel(x, y)
                cell = QRectF(x, y, 1, 1)
                painter.drawRect(cell)
                painter.setPen(Qt.GlobalColor.white)
                painter.drawText(cell, Qt.AlignmentFlag.AlignCenter, f"{r},{g},{b}")
                painter.setPen(pen)
        painter.restore()

    def _apply_transform(self) -> None:
        transform = QTransform()
        transform.scale(self._scale, self._scale)
        self.setTransform(transform)
        self.zoomChanged.emit(self._scale)


class ImageWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Projekt 4 - PyQt6")
        self.resize(1280, 900)

        self.current_image: ImageBuffer | None = None
        self._qimage: QImage | None = None
        self.bezier_window = None  # Referencja do okna Béziera
        self.polygon_window = None  # Referencja do okna wielokątów

        self.view = ImageGraphicsView()
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.view)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        zoom_label = QLabel("Zoom:")
        controls.addWidget(zoom_label)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 1600)  # 0.1x - 16x
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self._on_slider_changed)
        controls.addWidget(self.zoom_slider)
        self.zoom_value_label = QLabel("100%")
        self.zoom_value_label.setMinimumWidth(60)
        controls.addWidget(self.zoom_value_label)
        layout.addLayout(controls)

        self.setCentralWidget(central_widget)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.view.zoomChanged.connect(self._on_zoom_changed)
        self.view.cursorMoved.connect(self._on_cursor_moved)

        self._build_menus()

    # Menu construction
    def _build_menus(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Plik")
        self._add_action(file_menu, "Otwórz...", self.open_image, shortcut="Ctrl+O")
        self._add_action(file_menu, "Zapisz jako JPEG...", self.save_as_jpeg)
        self._add_action(file_menu, "Zapisz jako PPM (ASCII)...", lambda: self.save_as_ppm(binary=False))
        self._add_action(file_menu, "Zapisz jako PPM (Binarny)...", lambda: self.save_as_ppm(binary=True))
        file_menu.addSeparator()
        self._add_action(file_menu, "Wyjście", self.close, shortcut="Ctrl+Q")

        point_menu = menubar.addMenu("Przekształcenia punktowe")
        self._add_action(point_menu, "Dodawanie", self.add_constant)
        self._add_action(point_menu, "Odejmowanie", self.subtract_constant)
        self._add_action(point_menu, "Mnożenie", self.multiply_constant)
        self._add_action(point_menu, "Dzielenie", self.divide_constant)
        self._add_action(point_menu, "Zmiana jasności", self.change_brightness)
        point_menu.addSeparator()
        self._add_action(point_menu, "Skala szarości (średnia)", self.grayscale_average)
        self._add_action(point_menu, "Skala szarości (luminancja)", self.grayscale_luminance)
        self._add_action(point_menu, "Skalowanie liniowe RGB", self.linear_scale)

        filter_menu = menubar.addMenu("Filtry")
        self._add_action(filter_menu, "Filtr uśredniający", self.apply_mean_filter)
        self._add_action(filter_menu, "Filtr medianowy", self.apply_median_filter)
        self._add_action(filter_menu, "Sobel (krawędzie)", self.apply_sobel)
        self._add_action(filter_menu, "Filtr wyostrzający", self.apply_sharpen)
        self._add_action(filter_menu, "Rozmycie Gaussa", self.apply_gaussian)
        self._add_action(filter_menu, "Dowolna maska", self.apply_custom_kernel)

        histogram_menu = menubar.addMenu("Histogram")
        self._add_action(histogram_menu, "Rozszerzenie histogramu (R)", lambda: self.histogram_stretch(0))
        self._add_action(histogram_menu, "Rozszerzenie histogramu (G)", lambda: self.histogram_stretch(1))
        self._add_action(histogram_menu, "Rozszerzenie histogramu (B)", lambda: self.histogram_stretch(2))
        self._add_action(histogram_menu, "Rozszerzenie histogramu (wszystkie)", lambda: self.histogram_stretch(None))
        histogram_menu.addSeparator()
        self._add_action(histogram_menu, "Wyrównanie histogramu (R)", lambda: self.histogram_equalize(0))
        self._add_action(histogram_menu, "Wyrównanie histogramu (G)", lambda: self.histogram_equalize(1))
        self._add_action(histogram_menu, "Wyrównanie histogramu (B)", lambda: self.histogram_equalize(2))
        self._add_action(histogram_menu, "Wyrównanie histogramu (wszystkie)", lambda: self.histogram_equalize(None))

        binarization_menu = menubar.addMenu("Binaryzacja")
        self._add_action(binarization_menu, "Ręcznie (próg)", self.threshold_manual)
        binarization_menu.addSeparator()
        self._add_action(binarization_menu, "Procentowa selekcja czarnego", self.threshold_percent_black)
        self._add_action(binarization_menu, "Selekcja iteratywna średniej", self.threshold_mean_iterative)
        self._add_action(binarization_menu, "Selekcja entropii", self.threshold_entropy)
        self._add_action(binarization_menu, "Błąd minimalny", self.threshold_minimum_error)
        self._add_action(binarization_menu, "Rozmyty błąd minimalny", self.threshold_fuzzy_minimum_error)

        tools_menu = menubar.addMenu("Narzędzia")
        self._add_action(tools_menu, "Krzywe Béziera...", self.open_bezier_window)
        self._add_action(tools_menu, "Wielokąty + transformacje...", self.open_polygon_window)

    def _add_action(self, menu: QMenu, text: str, handler: Callable, shortcut: str | None = None) -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(handler)
        menu.addAction(action)
        return action

    # File operations
    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Otwórz obraz",
            "",
            "Obrazy (*.ppm *.jpg *.jpeg);;PPM (*.ppm);;JPEG (*.jpg *.jpeg)",
        )
        if not path:
            return
        try:
            self.current_image = image_io.load_image(path)
            self._refresh_view()
            self.status_bar.showMessage(f"Wczytano: {Path(path).name}", 5000)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Błąd", f"Nie udało się wczytać obrazu:\n{exc}")

    def save_as_jpeg(self) -> None:
        if not self._require_image():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz jako JPEG", "", "JPEG (*.jpg *.jpeg)")
        if not path:
            return
        quality, ok = QInputDialog.getInt(self, "Jakość JPEG", "Podaj jakość (1-95):", 90, 1, 95)
        if not ok:
            return
        try:
            image_io.save_as_jpeg(self.current_image, path, quality=quality)  # type: ignore[arg-type]
            self.status_bar.showMessage(f"Zapisano JPEG (jakość {quality})", 5000)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Błąd", f"Nie udało się zapisać JPEG:\n{exc}")

    def save_as_ppm(self, binary: bool) -> None:
        if not self._require_image():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz jako PPM", "", "PPM (*.ppm)")
        if not path:
            return
        try:
            image_io.save_as_ppm(self.current_image, path, binary=binary)  # type: ignore[arg-type]
            fmt = "P6" if binary else "P3"
            self.status_bar.showMessage(f"Zapisano {fmt}: {Path(path).name}", 5000)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Błąd", f"Nie udało się zapisać PPM:\n{exc}")

    # Point operations
    def add_constant(self) -> None:
        self._apply_scalar_operation("Dodawanie", operations.add_constant)

    def subtract_constant(self) -> None:
        self._apply_scalar_operation("Odejmowanie", operations.subtract_constant)

    def multiply_constant(self) -> None:
        self._apply_scalar_operation("Mnożenie", operations.multiply)

    def divide_constant(self) -> None:
        self._apply_scalar_operation("Dzielenie", operations.divide)

    def change_brightness(self) -> None:
        self._apply_scalar_operation("Zmiana jasności", operations.change_brightness)

    def grayscale_average(self) -> None:
        self._apply_operation(operations.grayscale_average, "Skala szarości (średnia)")

    def grayscale_luminance(self) -> None:
        self._apply_operation(operations.grayscale_luminance, "Skala szarości (luminancja)")

    def linear_scale(self) -> None:
        if not self._require_image():
            return
        r = self._ask_float("Skalowanie R", 1.0)
        if r is None:
            return
        g = self._ask_float("Skalowanie G", 1.0)
        if g is None:
            return
        b = self._ask_float("Skalowanie B", 1.0)
        if b is None:
            return
        self._apply_operation(lambda img: operations.linear_color_scale(img, r, g, b), "Skalowanie liniowe RGB")

    # Filters
    def apply_mean_filter(self) -> None:
        size = self._ask_kernel_size()
        if size:
            self._apply_operation(lambda img: filters.mean_filter(img, size=size), f"Filtr uśredniający {size}x{size}")

    def apply_median_filter(self) -> None:
        size = self._ask_kernel_size()
        if size:
            self._apply_operation(lambda img: filters.median_filter(img, size=size), f"Filtr medianowy {size}x{size}")

    def apply_sobel(self) -> None:
        self._apply_operation(filters.sobel_edge, "Sobel")

    def apply_sharpen(self) -> None:
        self._apply_operation(filters.high_pass_sharpen, "Wyostrzanie")

    def apply_gaussian(self) -> None:
        sigma = self._ask_float("Sigma", 1.5, minimum=0.1)
        if sigma is not None:
            self._apply_operation(lambda img: filters.gaussian_blur(img, sigma=sigma), f"Gauss σ={sigma:.2f}")

    def apply_custom_kernel(self) -> None:
        size = self._ask_kernel_size()
        if not size:
            return
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Maska",
            "Podaj wartości maski (wiersze oddzielone enterem, wartości spacjami):",
        )
        if not ok or not text.strip():
            return
        try:
            rows = [list(map(float, line.split())) for line in text.strip().splitlines()]
        except ValueError:
            QMessageBox.warning(self, "Błąd", "Niepoprawny format maski.")
            return
        if len(rows) != size or any(len(row) != size for row in rows):
            QMessageBox.warning(self, "Błąd", "Liczba wartości nie zgadza się z rozmiarem maski.")
            return
        divisor = self._ask_float("Dzielnik (opcjonalny)", 0.0, allow_cancel=True)
        offset = self._ask_float("Offset", 0.0, allow_cancel=True)
        kwargs = {}
        if divisor is not None and divisor != 0:
            kwargs["divisor"] = divisor
        if offset is not None and offset != 0:
            kwargs["offset"] = offset
        self._apply_operation(lambda img: filters.custom_convolution(img, rows, **kwargs), "Własna maska")

    # Histogram operations
    def histogram_stretch(self, channel: int | None) -> None:
        if not self._require_image():
            return
        if channel is None:
            self._apply_operation(histogram.histogram_stretch, "Rozszerzenie histogramu (wszystkie)")
        else:
            ch_name = ["R", "G", "B"][channel]
            self._apply_operation(lambda img: histogram.histogram_stretch(img, channel), f"Rozszerzenie histogramu ({ch_name})")

    def histogram_equalize(self, channel: int | None) -> None:
        if not self._require_image():
            return
        if channel is None:
            self._apply_operation(histogram.histogram_equalization, "Wyrównanie histogramu (wszystkie)")
        else:
            ch_name = ["R", "G", "B"][channel]
            self._apply_operation(lambda img: histogram.histogram_equalization(img, channel), f"Wyrównanie histogramu ({ch_name})")

    # Binarization operations
    def threshold_manual(self) -> None:
        if not self._require_image():
            return
        threshold, ok = QInputDialog.getInt(self, "Próg binaryzacji", "Podaj próg (0-255):", 128, 0, 255)
        if not ok:
            return
        self._apply_operation(lambda img: binarization.threshold_manual(img, threshold), f"Binaryzacja (próg={threshold})")

    def threshold_percent_black(self) -> None:
        if not self._require_image():
            return
        percent, ok = QInputDialog.getDouble(self, "Procentowa selekcja czarnego", "Podaj procent czarnego (0-100):", 50.0, 0.0, 100.0, 1)
        if not ok:
            return
        self._apply_operation(lambda img: binarization.threshold_percent_black(img, percent), f"Binaryzacja (procent czarnego={percent:.1f}%)")

    def threshold_mean_iterative(self) -> None:
        self._apply_operation(binarization.threshold_mean_iterative, "Binaryzacja (iteratywna średnia)")

    def threshold_entropy(self) -> None:
        self._apply_operation(binarization.threshold_entropy, "Binaryzacja (entropia)")

    def threshold_minimum_error(self) -> None:
        self._apply_operation(binarization.threshold_minimum_error, "Binaryzacja (błąd minimalny)")

    def threshold_fuzzy_minimum_error(self) -> None:
        self._apply_operation(binarization.threshold_fuzzy_minimum_error, "Binaryzacja (rozmyty błąd minimalny)")

    # Helpers
    def _apply_scalar_operation(self, title: str, func: Callable[[ImageBuffer, float], ImageBuffer]) -> None:
        value = self._ask_float(title, 0.0)
        if value is None:
            return
        self._apply_operation(lambda img: func(img, value), f"{title}: {value}")

    def _apply_operation(self, func: Callable[[ImageBuffer], ImageBuffer], label: str) -> None:
        if not self._require_image():
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.current_image = func(self.current_image)  # type: ignore[arg-type]
            self._refresh_view()
            self.status_bar.showMessage(label, 4000)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Błąd", f"Operacja nie powiodła się:\n{exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def _refresh_view(self) -> None:
        if not self.current_image:
            return
        self._qimage = _buffer_to_qimage(self.current_image)
        pixmap = QPixmap.fromImage(self._qimage)
        self.view.set_image(pixmap, self.current_image)
        self.view.fit_image()

    def _on_slider_changed(self, value: int) -> None:
        self.view.set_scale(value / 100.0, user_initiated=True)

    def _on_zoom_changed(self, scale: float) -> None:
        slider_value = int(scale * 100)
        if self.zoom_slider.value() != slider_value:
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(slider_value)
            self.zoom_slider.blockSignals(False)
        self.zoom_value_label.setText(f"{scale * 100:.0f}%")

    def _on_cursor_moved(self, x: int, y: int, color: tuple[int, int, int] | None) -> None:
        if color:
            self.status_bar.showMessage(f"X:{x} Y:{y} | R:{color[0]} G:{color[1]} B:{color[2]}")
        else:
            self.status_bar.showMessage("Poza obrazem")

    def _ask_float(
        self,
        title: str,
        default: float,
        minimum: float | None = None,
        maximum: float | None = None,
        allow_cancel: bool = True,
    ) -> float | None:
        min_val = minimum if minimum is not None else -1e9
        max_val = maximum if maximum is not None else 1e9
        value, ok = QInputDialog.getDouble(self, title, "Podaj wartość:", default, min_val, max_val, decimals=3)
        if not ok:
            return None if allow_cancel else default
        return value

    def _ask_kernel_size(self) -> int | None:
        size, ok = QInputDialog.getInt(self, "Rozmiar maski", "Podaj nieparzysty rozmiar (3,5,...):", 3, 1, 15, 1)
        if not ok:
            return None
        if size % 2 == 0:
            QMessageBox.warning(self, "Błąd", "Rozmiar maski musi być nieparzysty.")
            return None
        return size

    def _require_image(self) -> bool:
        if self.current_image is None:
            QMessageBox.information(self, "Informacja", "Najpierw wczytaj obraz.")
            return False
        return True

    def open_bezier_window(self) -> None:
        """Otwiera okno do rysowania krzywych Béziera."""
        from .bezier_window import BezierWindow
        
        if self.bezier_window is None or not self.bezier_window.isVisible():
            self.bezier_window = BezierWindow()
            self.bezier_window.show()
        else:
            self.bezier_window.activateWindow()
            self.bezier_window.raise_()

    def open_polygon_window(self) -> None:
        """Otwiera okno do rysowania wielokątów i transformacji 2D (macierze jednorodne)."""
        from .polygon_window import PolygonWindow

        if self.polygon_window is None or not self.polygon_window.isVisible():
            self.polygon_window = PolygonWindow()
            self.polygon_window.show()
        else:
            self.polygon_window.activateWindow()
            self.polygon_window.raise_()


def run_app() -> None:
    import sys

    app = QApplication(sys.argv)
    window = ImageWindow()
    window.show()
    sys.exit(app.exec())

