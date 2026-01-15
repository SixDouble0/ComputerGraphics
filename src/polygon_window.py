from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .geometry2d import Polygon, Vec2, around_point, mat3_rotate_degrees, mat3_scale, mat3_translate


ToolMode = Literal["select", "draw", "move", "rotate", "scale", "set_pivot"]


@dataclass
class SceneState:
    polygons: list[Polygon]
    selected_index: int | None = None
    rotate_pivot: Vec2 = (200.0, 200.0)
    scale_pivot: Vec2 = (200.0, 200.0)


class PolygonCanvas(QWidget):
    def __init__(self, state: SceneState, persist_path: Path) -> None:
        super().__init__()
        self.setMinimumSize(900, 650)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: white;")

        self.state = state
        self.persist_path = persist_path

        self.mode: ToolMode = "select"
        self._draft: list[Vec2] = []
        self._drag_last: Vec2 | None = None
        self._rotate_start_angle: float | None = None
        self._scale_start_dist: float | None = None

        self.vertex_radius = 6.0

    def set_mode(self, mode: ToolMode) -> None:
        self.mode = mode
        self._draft.clear()
        self._drag_last = None
        self._rotate_start_angle = None
        self._scale_start_dist = None
        self.update()

    def selected_polygon(self) -> Polygon | None:
        if self.state.selected_index is None:
            return None
        if 0 <= self.state.selected_index < len(self.state.polygons):
            return self.state.polygons[self.state.selected_index]
        return None

    def clear_scene(self) -> None:
        self.state.polygons.clear()
        self.state.selected_index = None
        self._draft.clear()
        self.save()
        self.update()

    def save(self) -> None:
        payload = {
            "version": 1,
            "rotate_pivot": {"x": self.state.rotate_pivot[0], "y": self.state.rotate_pivot[1]},
            "scale_pivot": {"x": self.state.scale_pivot[0], "y": self.state.scale_pivot[1]},
            "polygons": [p.to_dict() for p in self.state.polygons],
            "selected_index": self.state.selected_index,
        }
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        self.persist_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.persist_path.exists():
            return
        data = json.loads(self.persist_path.read_text(encoding="utf-8"))
        self.state.polygons = [Polygon.from_dict(p) for p in data.get("polygons", [])]
        rp = data.get("rotate_pivot", {})
        sp = data.get("scale_pivot", {})
        self.state.rotate_pivot = (float(rp.get("x", 200.0)), float(rp.get("y", 200.0)))
        self.state.scale_pivot = (float(sp.get("x", 200.0)), float(sp.get("y", 200.0)))
        sel = data.get("selected_index", None)
        self.state.selected_index = int(sel) if isinstance(sel, int) else None
        self.update()

    def _pos(self, event) -> Vec2:
        p = event.position()
        return (float(p.x()), float(p.y()))

    def _select_at(self, pos: Vec2) -> None:
        self.state.selected_index = None
        for i in range(len(self.state.polygons) - 1, -1, -1):
            if self.state.polygons[i].hit_test(pos):
                self.state.selected_index = i
                break
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        pos = self._pos(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.mode == "draw":
            # LPM - dodaj wierzchołek, a jeśli blisko pierwszego i mamy >=3 to zamknij
            if len(self._draft) >= 3:
                d2 = (pos[0] - self._draft[0][0]) ** 2 + (pos[1] - self._draft[0][1]) ** 2
                if d2 <= (self.vertex_radius * 2) ** 2:
                    poly = Polygon(points=list(self._draft), name=f"Wielokąt {len(self.state.polygons)+1}")
                    self.state.polygons.append(poly)
                    self.state.selected_index = len(self.state.polygons) - 1
                    self._draft.clear()
                    self.save()
                    self.update()
                    return
            self._draft.append(pos)
            self.update()
            return

        if self.mode == "set_pivot":
            # ustaw pivot dla obrotu i skali (w zależności od tego, co user wybrał w UI)
            # Canvas nie wie który; window zmieni pivoty bezpośrednio przez state.
            self._drag_last = pos
            return

        # select / transform modes
        self._select_at(pos)
        if self.selected_polygon() is None:
            return
        self._drag_last = pos

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        pos = self._pos(event)
        poly = self.selected_polygon()
        if self._drag_last is None or poly is None:
            return

        if self.mode in ("select", "move"):
            dx = pos[0] - self._drag_last[0]
            dy = pos[1] - self._drag_last[1]
            poly.apply(mat3_translate(dx, dy))
            self._drag_last = pos
            self.update()
            return

        if self.mode == "rotate":
            pivot = self.state.rotate_pivot
            import math

            ang = math.degrees(math.atan2(pos[1] - pivot[1], pos[0] - pivot[0]))
            if self._rotate_start_angle is None:
                self._rotate_start_angle = ang
                return
            delta = ang - self._rotate_start_angle
            poly.apply(around_point(pivot, mat3_rotate_degrees(delta)))
            self._rotate_start_angle = ang
            self.update()
            return

        if self.mode == "scale":
            pivot = self.state.scale_pivot
            import math

            dist = math.hypot(pos[0] - pivot[0], pos[1] - pivot[1])
            if self._scale_start_dist is None:
                self._scale_start_dist = max(1e-6, dist)
                return
            factor = dist / self._scale_start_dist
            poly.apply(around_point(pivot, mat3_scale(factor, factor)))
            self._scale_start_dist = max(1e-6, dist)
            self.update()
            return

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._drag_last is not None:
            self._drag_last = None
            self._rotate_start_angle = None
            self._scale_start_dist = None
            self.save()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # pivots
        self._draw_pivot(painter, self.state.rotate_pivot, QColor(80, 80, 255), "R")
        self._draw_pivot(painter, self.state.scale_pivot, QColor(0, 160, 0), "S")

        # polygons
        for i, poly in enumerate(self.state.polygons):
            selected = i == self.state.selected_index
            self._draw_polygon(painter, poly, selected=selected)

        # draft
        if len(self._draft) >= 1:
            pen = QPen(QColor(120, 120, 120), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            for i in range(len(self._draft) - 1):
                painter.drawLine(QPointF(*self._draft[i]), QPointF(*self._draft[i + 1]))
            for p in self._draft:
                self._draw_vertex(painter, p, QColor(255, 120, 0))
            painter.drawText(10, 20, "Tryb rysowania: klikaj aby dodać wierzchołki, kliknij przy pierwszym aby zamknąć.")

    def _draw_polygon(self, painter: QPainter, poly: Polygon, selected: bool) -> None:
        if len(poly.points) < 2:
            return
        pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(pen)
        if selected:
            painter.setBrush(QColor(255, 235, 200))
        else:
            painter.setBrush(QColor(230, 230, 230))

        qpts = [QPointF(x, y) for x, y in poly.points]
        painter.drawPolygon(*qpts)

        for p in poly.points:
            self._draw_vertex(painter, p, QColor(220, 0, 0) if selected else QColor(120, 0, 0))

    def _draw_vertex(self, painter: QPainter, p: Vec2, color: QColor) -> None:
        painter.setBrush(color)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawEllipse(QPointF(p[0], p[1]), self.vertex_radius, self.vertex_radius)

    def _draw_pivot(self, painter: QPainter, p: Vec2, color: QColor, label: str) -> None:
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        r = 10
        painter.drawEllipse(QPointF(p[0], p[1]), r, r)
        painter.drawLine(QPointF(p[0] - r, p[1]), QPointF(p[0] + r, p[1]))
        painter.drawLine(QPointF(p[0], p[1] - r), QPointF(p[0], p[1] + r))
        painter.drawText(int(p[0] + r + 4), int(p[1] - r - 2), label)


class PolygonWindow(QWidget):
    """Okno do rysowania wielokątów i wykonywania transformacji (macierze jednorodne 3x3)."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Figury: wielokąty + transformacje jednorodne")
        self.resize(1200, 750)

        persist_path = Path.cwd() / "polygons.json"
        self.state = SceneState(polygons=[])
        self.canvas = PolygonCanvas(self.state, persist_path=persist_path)
        self.canvas.load()

        panel = self._create_panel()
        main = QHBoxLayout()
        main.addWidget(self.canvas, stretch=1)
        main.addLayout(panel)
        self.setLayout(main)

    def _create_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()

        title = QLabel("Wielokąty")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        info = QLabel(
            "Wymagania:\n"
            "- rysowanie wielokątów (mysz)\n"
            "- chwytanie figur myszą\n"
            "- przesunięcie/obrót/skala (mysz i pola)\n"
            "- współrzędne jednorodne (macierze 3x3)\n"
            "- zapis/odczyt (polygons.json)\n\n"
            "Sterowanie:\n"
            "- Draw: klikaj wierzchołki, kliknij przy pierwszym aby zamknąć\n"
            "- Move: przeciągaj\n"
            "- Rotate/Scale: przeciągaj względem pivotu\n"
        )
        info.setStyleSheet("color: #555;")
        layout.addWidget(info)

        tools = QGroupBox("Tryb")
        tools_layout = QVBoxLayout()
        self.rb_select = QRadioButton("Select")
        self.rb_draw = QRadioButton("Draw polygon")
        self.rb_move = QRadioButton("Move")
        self.rb_rotate = QRadioButton("Rotate")
        self.rb_scale = QRadioButton("Scale")
        self.rb_select.setChecked(True)

        for rb in (self.rb_select, self.rb_draw, self.rb_move, self.rb_rotate, self.rb_scale):
            tools_layout.addWidget(rb)
        tools.setLayout(tools_layout)
        layout.addWidget(tools)

        self.rb_select.toggled.connect(lambda v: v and self.canvas.set_mode("select"))
        self.rb_draw.toggled.connect(lambda v: v and self.canvas.set_mode("draw"))
        self.rb_move.toggled.connect(lambda v: v and self.canvas.set_mode("move"))
        self.rb_rotate.toggled.connect(lambda v: v and self.canvas.set_mode("rotate"))
        self.rb_scale.toggled.connect(lambda v: v and self.canvas.set_mode("scale"))

        # Translate (text)
        tr_group = QGroupBox("Przesunięcie (tekst)")
        tr_l = QVBoxLayout()
        tr_row = QHBoxLayout()
        tr_row.addWidget(QLabel("dx:"))
        self.dx = QDoubleSpinBox()
        self.dx.setRange(-5000, 5000)
        self.dx.setValue(10)
        tr_row.addWidget(self.dx)
        tr_row.addWidget(QLabel("dy:"))
        self.dy = QDoubleSpinBox()
        self.dy.setRange(-5000, 5000)
        self.dy.setValue(10)
        tr_row.addWidget(self.dy)
        tr_l.addLayout(tr_row)
        tr_btn = QPushButton("Zastosuj przesunięcie")
        tr_btn.clicked.connect(self._apply_translate_text)
        tr_l.addWidget(tr_btn)
        tr_group.setLayout(tr_l)
        layout.addWidget(tr_group)

        # Rotate (text + pivot)
        rot_group = QGroupBox("Obrót (tekst)")
        rot_l = QVBoxLayout()
        rot_row = QHBoxLayout()
        rot_row.addWidget(QLabel("kąt (°):"))
        self.angle = QDoubleSpinBox()
        self.angle.setRange(-3600, 3600)
        self.angle.setValue(15)
        rot_row.addWidget(self.angle)
        rot_l.addLayout(rot_row)

        rp_row = QHBoxLayout()
        rp_row.addWidget(QLabel("pivot X:"))
        self.rpx = QDoubleSpinBox()
        self.rpx.setRange(-5000, 5000)
        self.rpx.setValue(self.state.rotate_pivot[0])
        rp_row.addWidget(self.rpx)
        rp_row.addWidget(QLabel("Y:"))
        self.rpy = QDoubleSpinBox()
        self.rpy.setRange(-5000, 5000)
        self.rpy.setValue(self.state.rotate_pivot[1])
        rp_row.addWidget(self.rpy)
        rot_l.addLayout(rp_row)

        set_rp = QPushButton("Ustaw pivot obrotu (z pól)")
        set_rp.clicked.connect(self._set_rotate_pivot_text)
        rot_l.addWidget(set_rp)

        rot_btn = QPushButton("Zastosuj obrót")
        rot_btn.clicked.connect(self._apply_rotate_text)
        rot_l.addWidget(rot_btn)
        rot_group.setLayout(rot_l)
        layout.addWidget(rot_group)

        # Scale (text + pivot)
        sc_group = QGroupBox("Skalowanie (tekst)")
        sc_l = QVBoxLayout()
        sc_row = QHBoxLayout()
        sc_row.addWidget(QLabel("współczynnik:"))
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.01, 100.0)
        self.scale.setDecimals(4)
        self.scale.setValue(1.1)
        sc_row.addWidget(self.scale)
        sc_l.addLayout(sc_row)

        sp_row = QHBoxLayout()
        sp_row.addWidget(QLabel("pivot X:"))
        self.spx = QDoubleSpinBox()
        self.spx.setRange(-5000, 5000)
        self.spx.setValue(self.state.scale_pivot[0])
        sp_row.addWidget(self.spx)
        sp_row.addWidget(QLabel("Y:"))
        self.spy = QDoubleSpinBox()
        self.spy.setRange(-5000, 5000)
        self.spy.setValue(self.state.scale_pivot[1])
        sp_row.addWidget(self.spy)
        sc_l.addLayout(sp_row)

        set_sp = QPushButton("Ustaw pivot skali (z pól)")
        set_sp.clicked.connect(self._set_scale_pivot_text)
        sc_l.addWidget(set_sp)

        sc_btn = QPushButton("Zastosuj skalowanie")
        sc_btn.clicked.connect(self._apply_scale_text)
        sc_l.addWidget(sc_btn)
        sc_group.setLayout(sc_l)
        layout.addWidget(sc_group)

        # Save/load/clear
        actions = QGroupBox("Scena")
        a_l = QVBoxLayout()
        btn_save = QPushButton("Zapisz (JSON)")
        btn_save.clicked.connect(self.canvas.save)
        btn_load = QPushButton("Wczytaj (JSON)")
        btn_load.clicked.connect(self.canvas.load)
        btn_clear = QPushButton("Wyczyść scenę")
        btn_clear.clicked.connect(self.canvas.clear_scene)
        a_l.addWidget(btn_save)
        a_l.addWidget(btn_load)
        a_l.addWidget(btn_clear)
        actions.setLayout(a_l)
        layout.addWidget(actions)

        layout.addStretch()
        return layout

    def _apply_translate_text(self) -> None:
        poly = self.canvas.selected_polygon()
        if poly is None:
            return
        poly.apply(mat3_translate(self.dx.value(), self.dy.value()))
        self.canvas.save()
        self.canvas.update()

    def _set_rotate_pivot_text(self) -> None:
        self.state.rotate_pivot = (self.rpx.value(), self.rpy.value())
        self.canvas.save()
        self.canvas.update()

    def _apply_rotate_text(self) -> None:
        poly = self.canvas.selected_polygon()
        if poly is None:
            return
        pivot = self.state.rotate_pivot
        poly.apply(around_point(pivot, mat3_rotate_degrees(self.angle.value())))
        self.canvas.save()
        self.canvas.update()

    def _set_scale_pivot_text(self) -> None:
        self.state.scale_pivot = (self.spx.value(), self.spy.value())
        self.canvas.save()
        self.canvas.update()

    def _apply_scale_text(self) -> None:
        poly = self.canvas.selected_polygon()
        if poly is None:
            return
        pivot = self.state.scale_pivot
        s = self.scale.value()
        poly.apply(around_point(pivot, mat3_scale(s, s)))
        self.canvas.save()
        self.canvas.update()


