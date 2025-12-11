"""
Okno do rysowania i edycji krzywych Béziera.
"""
from __future__ import annotations

from typing import Sequence

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .bezier import generate_bezier_curve


class BezierCanvas(QWidget):
    """Canvas do rysowania krzywej Béziera z obsługą myszy."""
    
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        
        self.control_points: list[tuple[float, float]] = []
        self.weights: list[float] = []
        self.curve_points: list[tuple[float, float]] = []
        
        self.dragging_index: int | None = None
        self.hover_index: int | None = None
        self.point_radius = 6
        self.use_rational = False
        self.default_weight = 1.0
        
        self.setStyleSheet("background-color: white;")
    
    def set_rational_mode(self, enabled: bool) -> None:
        """Włącza/wyłącza tryb wymiernej krzywej Béziera."""
        self.use_rational = enabled
        self._update_curve()
    
    def set_control_points(self, points: Sequence[tuple[float, float]]) -> None:
        """Ustawia punkty kontrolne z zewnątrz (np. z pól tekstowych)."""
        self.control_points = list(points)
        self.weights = [self.default_weight] * len(self.control_points)
        self._update_curve()
    
    def set_weight(self, index: int, weight: float) -> None:
        """Ustawia wagę dla punktu o danym indeksie."""
        if 0 <= index < len(self.weights):
            self.weights[index] = weight
            self._update_curve()
    
    def clear_points(self) -> None:
        """Usuwa wszystkie punkty kontrolne."""
        self.control_points.clear()
        self.weights.clear()
        self.curve_points.clear()
        self.dragging_index = None
        self.hover_index = None
        self.update()
    
    def _update_curve(self) -> None:
        """Przelicza krzywą Béziera na podstawie punktów kontrolnych."""
        if len(self.control_points) < 2:
            self.curve_points = list(self.control_points)
        else:
            weights = self.weights if self.use_rational else None
            self.curve_points = generate_bezier_curve(
                self.control_points,
                num_samples=200,
                weights=weights
            )
        self.update()
    
    def _find_point_at(self, x: float, y: float) -> int | None:
        """Znajduje indeks punktu kontrolnego w pobliżu danej pozycji."""
        for i, (px, py) in enumerate(self.control_points):
            dx = px - x
            dy = py - y
            if dx * dx + dy * dy <= self.point_radius ** 2:
                return i
        return None
    
    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        """Obsługa kliknięcia myszy - dodawanie lub rozpoczęcie przeciągania punktu."""
        x, y = event.position().x(), event.position().y()
        
        if event.button() == Qt.MouseButton.LeftButton:
            index = self._find_point_at(x, y)
            if index is not None:
                # Rozpocznij przeciąganie istniejącego punktu
                self.dragging_index = index
            else:
                # Dodaj nowy punkt kontrolny
                self.control_points.append((x, y))
                self.weights.append(self.default_weight)
                self._update_curve()
        elif event.button() == Qt.MouseButton.RightButton:
            # Usuń punkt pod kursorem
            index = self._find_point_at(x, y)
            if index is not None:
                self.control_points.pop(index)
                self.weights.pop(index)
                self._update_curve()
    
    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        """Obsługa ruchu myszy - przeciąganie punktu lub hover."""
        x, y = event.position().x(), event.position().y()
        
        if self.dragging_index is not None:
            # Aktualizuj pozycję przeciąganego punktu w czasie rzeczywistym
            self.control_points[self.dragging_index] = (x, y)
            self._update_curve()
        else:
            # Sprawdź, czy kursor jest nad punktem kontrolnym
            self.hover_index = self._find_point_at(x, y)
            self.update()
    
    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        """Obsługa puszczenia przycisku myszy - zakończenie przeciągania."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging_index = None
    
    def paintEvent(self, event) -> None:  # type: ignore[override]
        """Rysuje krzywą Béziera, łamaną kontrolną i punkty kontrolne."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Rysuj łamaną kontrolną (linie między punktami kontrolnymi)
        if len(self.control_points) >= 2:
            pen = QPen(QColor(200, 200, 200), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            for i in range(len(self.control_points) - 1):
                p1 = QPointF(*self.control_points[i])
                p2 = QPointF(*self.control_points[i + 1])
                painter.drawLine(p1, p2)
        
        # Rysuj krzywą Béziera
        if len(self.curve_points) >= 2:
            pen = QPen(QColor(0, 100, 255), 2)
            painter.setPen(pen)
            for i in range(len(self.curve_points) - 1):
                p1 = QPointF(*self.curve_points[i])
                p2 = QPointF(*self.curve_points[i + 1])
                painter.drawLine(p1, p2)
        
        # Rysuj punkty kontrolne
        for i, (x, y) in enumerate(self.control_points):
            if i == self.dragging_index:
                color = QColor(255, 150, 0)  # Pomarańczowy dla przeciąganego
            elif i == self.hover_index:
                color = QColor(255, 100, 100)  # Czerwony dla hover
            else:
                color = QColor(255, 0, 0)  # Czerwony dla normalnych
            
            painter.setBrush(color)
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.drawEllipse(QPointF(x, y), self.point_radius, self.point_radius)
            
            # Rysuj numer punktu
            painter.setPen(QPen(Qt.GlobalColor.black))
            painter.drawText(int(x + 10), int(y - 10), f"P{i}")
            
            # Jeśli tryb wymierny, rysuj wagę
            if self.use_rational and i < len(self.weights):
                painter.drawText(int(x + 10), int(y + 5), f"w={self.weights[i]:.1f}")


class BezierWindow(QWidget):
    """Główne okno do tworzenia i edycji krzywych Béziera."""
    
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Krzywe Béziera")
        self.resize(1000, 700)
        
        # Canvas do rysowania
        self.canvas = BezierCanvas()
        
        # Panel sterowania
        control_panel = self._create_control_panel()
        
        # Layout główny
        main_layout = QHBoxLayout()
        main_layout.addWidget(self.canvas, stretch=1)
        main_layout.addLayout(control_panel)
        
        self.setLayout(main_layout)
    
    def _create_control_panel(self) -> QVBoxLayout:
        """Tworzy panel sterowania z przyciskami i opcjami."""
        layout = QVBoxLayout()
        
        # Nagłówek
        title = QLabel("Krzywa Béziera")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Informacje
        info = QLabel(
            "LPM - dodaj/przeciągnij punkt\n"
            "PPM - usuń punkt\n"
        )
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)
        
        # Checkbox dla trybu wymiernego
        self.rational_checkbox = QCheckBox("Krzywa wymierna (NURBS)")
        self.rational_checkbox.stateChanged.connect(self._on_rational_changed)
        layout.addWidget(self.rational_checkbox)
        
        # Stopień krzywej (tylko info)
        degree_layout = QHBoxLayout()
        degree_layout.addWidget(QLabel("Stopień krzywej:"))
        self.degree_label = QLabel("0")
        self.degree_label.setStyleSheet("font-weight: bold;")
        degree_layout.addWidget(self.degree_label)
        degree_layout.addStretch()
        layout.addLayout(degree_layout)
        
        # Liczba punktów
        points_layout = QHBoxLayout()
        points_layout.addWidget(QLabel("Punkty kontrolne:"))
        self.points_label = QLabel("0")
        self.points_label.setStyleSheet("font-weight: bold;")
        points_layout.addWidget(self.points_label)
        points_layout.addStretch()
        layout.addLayout(points_layout)
        
        layout.addSpacing(20)
        
        # Przyciski
        clear_btn = QPushButton("Wyczyść wszystko")
        clear_btn.clicked.connect(self._on_clear)
        layout.addWidget(clear_btn)
        
        # Sekcja do dodawania punktów tekstowo
        layout.addSpacing(20)
        add_point_label = QLabel("Dodaj punkt współrzędnymi:")
        add_point_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(add_point_label)
        
        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("X:"))
        self.x_spinbox = QDoubleSpinBox()
        self.x_spinbox.setRange(0, 2000)
        self.x_spinbox.setValue(100)
        coord_layout.addWidget(self.x_spinbox)
        
        coord_layout.addWidget(QLabel("Y:"))
        self.y_spinbox = QDoubleSpinBox()
        self.y_spinbox.setRange(0, 2000)
        self.y_spinbox.setValue(100)
        coord_layout.addWidget(self.y_spinbox)
        layout.addLayout(coord_layout)
        
        add_point_btn = QPushButton("Dodaj punkt")
        add_point_btn.clicked.connect(self._on_add_point_manual)
        layout.addWidget(add_point_btn)
        
        # Sekcja wag (tylko dla trybu wymiernego)
        layout.addSpacing(20)
        weight_label = QLabel("Waga punktu (NURBS):")
        weight_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(weight_label)
        
        weight_layout = QHBoxLayout()
        weight_layout.addWidget(QLabel("Indeks:"))
        self.weight_index_spinbox = QSpinBox()
        self.weight_index_spinbox.setRange(0, 0)
        weight_layout.addWidget(self.weight_index_spinbox)
        layout.addLayout(weight_layout)
        
        weight_value_layout = QHBoxLayout()
        weight_value_layout.addWidget(QLabel("Waga:"))
        self.weight_spinbox = QDoubleSpinBox()
        self.weight_spinbox.setRange(-10.0, 10.0)
        self.weight_spinbox.setValue(1.0)
        self.weight_spinbox.setSingleStep(0.1)
        weight_value_layout.addWidget(self.weight_spinbox)
        layout.addLayout(weight_value_layout)
        
        set_weight_btn = QPushButton("Ustaw wagę")
        set_weight_btn.clicked.connect(self._on_set_weight)
        layout.addWidget(set_weight_btn)
        
        layout.addStretch()
        
        # Połącz sygnały do aktualizacji informacji
        self.canvas.update = self._wrap_canvas_update(self.canvas.update)
        
        return layout
    
    def _wrap_canvas_update(self, original_update):
        """Opakowuje metodę update canvas, aby aktualizować statystyki."""
        def wrapped():
            self._update_stats()
            original_update()
        return wrapped
    
    def _update_stats(self) -> None:
        """Aktualizuje wyświetlane statystyki."""
        num_points = len(self.canvas.control_points)
        degree = max(0, num_points - 1)
        self.points_label.setText(str(num_points))
        self.degree_label.setText(str(degree))
        self.weight_index_spinbox.setRange(0, max(0, num_points - 1))
    
    def _on_rational_changed(self, state: int) -> None:
        """Obsługuje zmianę trybu wymiernego."""
        enabled = state == Qt.CheckState.Checked.value
        self.canvas.set_rational_mode(enabled)
    
    def _on_clear(self) -> None:
        """Czyści wszystkie punkty kontrolne."""
        self.canvas.clear_points()
        self._update_stats()
    
    def _on_add_point_manual(self) -> None:
        """Dodaje punkt kontrolny na podstawie wartości z pól tekstowych."""
        x = self.x_spinbox.value()
        y = self.y_spinbox.value()
        self.canvas.control_points.append((x, y))
        self.canvas.weights.append(self.canvas.default_weight)
        self.canvas._update_curve()
        self._update_stats()
    
    def _on_set_weight(self) -> None:
        """Ustawia wagę dla wybranego punktu."""
        index = self.weight_index_spinbox.value()
        weight = self.weight_spinbox.value()
        self.canvas.set_weight(index, weight)


def show_bezier_window() -> BezierWindow:
    """Tworzy i wyświetla okno krzywych Béziera."""
    window = BezierWindow()
    window.show()
    return window
