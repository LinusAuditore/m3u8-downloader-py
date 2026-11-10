"""Material Design 1 (2014 规范) 主题与组件库，种子颜色 #3388BB。

遵循 Google Material Design 1 指南 (https://m1.material.io/)：
- Primary 500 = #3388BB，Primary 700 = #236B96，Primary 100 = #C2DDF0；
- 浅灰画布 (#F5F5F5) + 纯白 Paper 卡片 (#FFFFFF) + 2dp (2px) 微圆角 + Z-depth 阴影；
- 实心 Primary 顶栏 (App Bar, 56dp, 4dp 阴影)；
- 按钮 (36dp 高, 2dp 圆角) 带鼠标落点扩散的 Ink Ripple 水波纹动效；
- 输入框采用底部单横线设计，聚焦时 2dp 主色底线以 FastOutSlowIn 曲线从中心向两侧展开；
- 线性进度条采用 4dp 高无边框细条（底轨 Primary 100，填充 Primary 500）。
"""

from __future__ import annotations

import math
from typing import Literal

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QRectF,
     QSize,
    Qt,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Material Design 1 调色板（由种子色 #3388BB 推导的 50–900 阶色板与语义色）
# ---------------------------------------------------------------------------

SEED_COLOR = "#3388BB"

PRIMARY_50 = "#E6F1F8"
PRIMARY_100 = "#C2DDF0"
PRIMARY_200 = "#99C7E6"
PRIMARY_300 = "#70B0DC"
PRIMARY_400 = "#529CD4"
PRIMARY_500 = "#3388BB"
PRIMARY_600 = "#2C7CAE"
PRIMARY_700 = "#236B96"
PRIMARY_800 = "#1B5A80"
PRIMARY_900 = "#103F5C"

CANVAS_BG = "#F5F5F5"  # MD1 Grey 100
SURFACE_CARD = "#FFFFFF"  # MD1 Paper White
SURFACE_HOVER = "#EEEEEE"  # MD1 Grey 200
STATUSBAR_BG = "#EEEEEE"

TEXT_PRIMARY = "#212121"  # 87% Black
TEXT_SECONDARY = "#757575"  # 54% Black
TEXT_HINT = "#9E9E9E"  # 38% Black
TEXT_DISABLED = "#9E9E9E"  # 38% Black
TEXT_ON_PRIMARY = "#FFFFFF"  # 100% White

DIVIDER = "#E0E0E0"  # 12% Black / Grey 300
INPUT_LINE_IDLE = "#949494"  # 42% Black (AA 3:1 contrast)
INPUT_LINE_DISABLED = "#BDBDBD"

STATUS_PENDING = "#E0E0E0"  # MD1 Grey 300
STATUS_PENDING_TEXT = "#616161"  # MD1 Grey 700
STATUS_DOWNLOADING = PRIMARY_500
STATUS_DONE = "#4CAF50"  # MD1 Green 500
STATUS_FAILED = "#F44336"  # MD1 Red 500
STATUS_WARNING = "#FFA000"  # MD1 Amber 700

CORNER_RADIUS = 2.0
BUTTON_HEIGHT = 36
BUTTON_MIN_WIDTH = 88
APPBAR_HEIGHT = 56


def fast_out_slow_in() -> QEasingCurve:
    """MD1 标准缓动曲线 cubic-bezier(0.4, 0.0, 0.2, 1)。"""
    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(
        QPointF(0.4, 0.0),
        QPointF(0.2, 1.0),
        QPointF(1.0, 1.0),
    )
    return curve


def apply_elevation(
    widget: QWidget,
    dp: int = 2,
    *,
    color: QColor | None = None,
) -> QGraphicsDropShadowEffect:
    """为控件挂载 Material Design 1 Z-depth 投影。"""
    effect = QGraphicsDropShadowEffect(widget)
    blur_map = {1: 4.0, 2: 8.0, 3: 10.0, 4: 12.0, 6: 16.0, 8: 20.0, 24: 32.0}
    offset_map = {1: 1.0, 2: 2.0, 3: 2.5, 4: 3.0, 6: 4.0, 8: 5.0, 24: 10.0}
    effect.setBlurRadius(blur_map.get(dp, float(dp * 3)))
    effect.setOffset(0.0, offset_map.get(dp, float(max(1, dp // 2))))
    effect.setColor(color or QColor(0, 0, 0, 42))
    widget.setGraphicsEffect(effect)
    return effect


# ---------------------------------------------------------------------------
# 全局主题样式表与 QPalette
# ---------------------------------------------------------------------------

GLOBAL_QSS = f"""
QMainWindow, QDialog {{
    background-color: {CANVAS_BG};
    color: {TEXT_PRIMARY};
}}

QLabel {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
}}

QScrollArea {{
    background-color: {SURFACE_CARD};
    border: 1px solid {DIVIDER};
    border-radius: 2px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #BDBDBD;
    min-height: 24px;
    border-radius: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {PRIMARY_500};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #BDBDBD;
    min-width: 24px;
    border-radius: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {PRIMARY_500};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QStatusBar {{
    background-color: {STATUSBAR_BG};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {DIVIDER};
    font-size: 12px;
    padding: 2px 12px;
}}
QStatusBar::item {{
    border: none;
}}

QToolTip {{
    background-color: #616161;
    color: #FFFFFF;
    border: none;
    border-radius: 2px;
    padding: 4px 8px;
    font-size: 12px;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {DIVIDER};
    selection-background-color: {PRIMARY_50};
    selection-color: {PRIMARY_700};
    outline: none;
    padding: 4px 0px;
}}
"""


def _select_preferred_font() -> QFont:
    families = set(QFontDatabase.families())
    candidates = [
        "Roboto",
        "Noto Sans CJK SC",
        "PingFang SC",
        "Hiragino Sans GB",
        "Microsoft YaHei",
        "Segoe UI",
        "Helvetica Neue",
    ]
    chosen = [name for name in candidates if name in families]
    font = QFont(chosen[0] if chosen else "")
    if chosen and hasattr(font, "setFamilies"):
        font.setFamilies(chosen)
    font.setPointSize(13)
    return font


def apply_material_theme(app: QApplication | None = None) -> None:
    """向 QApplication 注入 Material Design 1 (#3388BB) 调色板与全局样式。"""
    target = app or QApplication.instance()
    if not isinstance(target, QApplication):
        return

    target.setStyle("Fusion")
    target.setFont(_select_preferred_font())

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(CANVAS_BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(SURFACE_CARD))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#FAFAFA"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#616161"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_HINT))
    palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(PRIMARY_500))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Link, QColor(PRIMARY_500))

    disabled_color = QColor(TEXT_DISABLED)
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_color
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_color
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_color
    )

    target.setPalette(palette)
    target.setStyleSheet(GLOBAL_QSS)
    target.setProperty("_md1_theme_applied", True)


def ensure_material_theme() -> None:
    """若当前 QApplication 尚未应用 MD1 主题，则自动应用（方便单测直建窗口）。"""
    app = QApplication.instance()
    if isinstance(app, QApplication) and not app.property("_md1_theme_applied"):
        apply_material_theme(app)


# ---------------------------------------------------------------------------
# Material Design 1 核心组件
# ---------------------------------------------------------------------------

ButtonVariant = Literal["primary", "raised", "flat", "appbar"]


class MdButton(QPushButton):
    """Material Design 1 按钮（2dp 圆角、36dp 高度、Ink Ripple 水波纹动效）。"""

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        *,
        variant: ButtonVariant = "raised",
    ) -> None:
        super().__init__(text, parent)
        self._variant: ButtonVariant = variant
        self._hovered = False
        self._pressed = False
        self._ripple_center = QPointF(0.0, 0.0)
        self._ripple_radius = 0.0
        self._ripple_max_radius = 0.0
        self._ripple_opacity = 0.0

        self.setMinimumHeight(BUTTON_HEIGHT)
        self.setFixedHeight(BUTTON_HEIGHT)
        self.setMinimumWidth(BUTTON_MIN_WIDTH if variant != "appbar" else 72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self._expand_anim = QVariantAnimation(self)
        self._expand_anim.setDuration(200)
        self._expand_anim.setEasingCurve(fast_out_slow_in())
        self._expand_anim.valueChanged.connect(self._on_expand_tick)

        self._fade_anim = QVariantAnimation(self)
        self._fade_anim.setDuration(180)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._fade_anim.valueChanged.connect(self._on_fade_tick)

    @property
    def variant(self) -> ButtonVariant:
        return self._variant

    def set_variant(self, variant: ButtonVariant) -> None:
        self._variant = variant
        self.update()

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self.text())
        min_w = BUTTON_MIN_WIDTH if self._variant != "appbar" else 72
        width = max(min_w, text_width + 32, base.width())
        return QSize(width, BUTTON_HEIGHT)

    def _on_expand_tick(self, value: object) -> None:
        self._ripple_radius = float(value)
        self.update()

    def _on_fade_tick(self, value: object) -> None:
        self._ripple_opacity = float(value)
        self.update()

    def _start_ripple(self, pos: QPointF) -> None:
        self._ripple_center = pos
        w, h = float(self.width()), float(self.height())
        dx = max(pos.x(), w - pos.x())
        dy = max(pos.y(), h - pos.y())
        self._ripple_max_radius = math.hypot(dx, dy)
        self._ripple_opacity = 0.28 if self._variant in ("primary", "appbar") else 0.18
        self._fade_anim.stop()
        self._expand_anim.stop()
        self._expand_anim.setStartValue(max(6.0, self._ripple_max_radius * 0.12))
        self._expand_anim.setEndValue(self._ripple_max_radius)
        self._expand_anim.start()

    def _fade_out_ripple(self) -> None:
        if self._ripple_opacity <= 0.0:
            return
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._ripple_opacity)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._pressed = True
            self._start_ripple(event.position())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._pressed:
            self._pressed = False
            self._fade_out_ripple()
        super().mouseReleaseEvent(event)

    def hideEvent(self, event) -> None:
        self._expand_anim.stop()
        self._fade_anim.stop()
        self._ripple_opacity = 0.0
        super().hideEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect())
        enabled = self.isEnabled()

        # Raised 按钮预留底部 2px 轻投影空间
        is_raised = self._variant in ("primary", "raised")
        body_rect = rect.adjusted(0.5, 0.5, -0.5, -2.0 if is_raised else -0.5)

        path = QPainterPath()
        path.addRoundedRect(body_rect, CORNER_RADIUS, CORNER_RADIUS)

        # 1. 绘制 Raised 按钮的 2dp 底部阴影（压下时加深）
        if is_raised and enabled:
            shadow_offset = 2.0 if self._pressed else 1.5
            shadow_alpha = 55 if self._pressed else 36
            shadow_rect = body_rect.translated(0.0, shadow_offset)
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(shadow_rect, CORNER_RADIUS, CORNER_RADIUS)
            painter.fillPath(shadow_path, QColor(0, 0, 0, shadow_alpha))

        # 2. 绘制按钮底色与文字颜色
        if not enabled:
            if is_raised:
                bg_color = QColor(0, 0, 0, 31)  # 12% Black
            else:
                bg_color = QColor(0, 0, 0, 0)
            text_color = (
                QColor(255, 255, 255, 90)
                if self._variant == "appbar"
                else QColor(0, 0, 0, 66)  # 26% Black
            )
            ripple_rgb = (0, 0, 0)
        elif self._variant == "primary":
            if self._pressed:
                bg_color = QColor(PRIMARY_700)
            elif self._hovered:
                bg_color = QColor(PRIMARY_600)
            else:
                bg_color = QColor(PRIMARY_500)
            text_color = QColor(TEXT_ON_PRIMARY)
            ripple_rgb = (255, 255, 255)
        elif self._variant == "raised":
            if self._pressed:
                bg_color = QColor(DIVIDER)
            elif self._hovered:
                bg_color = QColor(SURFACE_HOVER)
            else:
                bg_color = QColor(SURFACE_CARD)
            text_color = QColor(TEXT_PRIMARY)
            ripple_rgb = (51, 136, 187)
        elif self._variant == "appbar":
            if self._pressed:
                bg_color = QColor(255, 255, 255, 42)
            elif self._hovered:
                bg_color = QColor(255, 255, 255, 24)
            else:
                bg_color = QColor(255, 255, 255, 0)
            text_color = QColor(TEXT_ON_PRIMARY)
            ripple_rgb = (255, 255, 255)
        else:  # flat
            if self._pressed:
                bg_color = QColor(51, 136, 187, 36)
            elif self._hovered:
                bg_color = QColor(51, 136, 187, 20)
            else:
                bg_color = QColor(0, 0, 0, 0)
            text_color = QColor(PRIMARY_500)
            ripple_rgb = (51, 136, 187)

        painter.fillPath(path, bg_color)

        # 白底 Raised 按钮加极浅顶边轮廓以增强层次
        if self._variant == "raised" and enabled:
            painter.setPen(QPen(QColor(0, 0, 0, 20), 1.0))
            painter.drawPath(path)

        # 3. 裁剪并绘制 Ink Ripple 水波纹
        if self._ripple_opacity > 0.005 and self._ripple_radius > 0.0:
            painter.save()
            painter.setClipPath(path)
            r, g, b = ripple_rgb
            ripple_color = QColor(r, g, b, int(255 * min(1.0, self._ripple_opacity)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(ripple_color)
            painter.drawEllipse(
                self._ripple_center, self._ripple_radius, self._ripple_radius
            )
            painter.restore()

        # 4. 绘制按钮文字（MD1 Medium 14px）
        font = QFont(self.font())
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(text_color)
        text = self.text().replace("&", "")
        painter.drawText(
            body_rect.adjusted(12.0, 0.0, -12.0, 0.0),
            int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine),
            text,
        )


class MdLineEdit(QLineEdit):
    """Material Design 1 单行文本输入框（底部单横线 + 中心展开的 2dp #3388BB 聚焦线）。"""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._hovered = False
        self._focus_progress = 1.0 if self.hasFocus() else 0.0

        self.setFrame(False)
        self.setMinimumHeight(34)
        self.setTextMargins(0, 4, 0, 6)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setStyleSheet(
            f"MdLineEdit {{ background: transparent; border: none; color: {TEXT_PRIMARY};"
            f" selection-background-color: {PRIMARY_200}; selection-color: {TEXT_PRIMARY}; }}"
            f"MdLineEdit:disabled {{ color: {TEXT_DISABLED}; }}"
        )

        self._focus_anim = QVariantAnimation(self)
        self._focus_anim.setDuration(180)
        self._focus_anim.setEasingCurve(fast_out_slow_in())
        self._focus_anim.valueChanged.connect(self._on_focus_tick)

    @property
    def focus_progress(self) -> float:
        return self._focus_progress

    def _on_focus_tick(self, value: object) -> None:
        self._focus_progress = float(value)
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._focus_anim.stop()
        self._focus_anim.setStartValue(self._focus_progress)
        self._focus_anim.setEndValue(1.0)
        self._focus_anim.start()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._focus_anim.stop()
        self._focus_anim.setStartValue(self._focus_progress)
        self._focus_anim.setEndValue(0.0)
        self._focus_anim.start()

    def hideEvent(self, event) -> None:
        self._focus_anim.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        w = float(self.width())
        y_base = float(self.height() - 1)

        if not self.isEnabled():
            pen = QPen(QColor(INPUT_LINE_DISABLED), 1.0, Qt.PenStyle.DotLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(0.0, y_base), QPointF(w, y_base))
            return

        # 1. 基础底线（Hover 时 2px 87% Black，Idle 时 1px 42% Black）
        if self._hovered and self._focus_progress < 1.0:
            painter.fillRect(
                QRectF(0.0, float(self.height() - 2), w, 2.0),
                QColor(TEXT_PRIMARY),
            )
        else:
            painter.fillRect(
                QRectF(0.0, y_base, w, 1.0),
                QColor(INPUT_LINE_IDLE),
            )

        # 2. 聚焦激活线（2dp Primary #3388BB，从中心向两侧展开）
        if self._focus_progress > 0.005:
            active_w = w * self._focus_progress
            x_left = (w - active_w) * 0.5
            painter.fillRect(
                QRectF(x_left, float(self.height() - 2), active_w, 2.0),
                QColor(PRIMARY_500),
            )


class MdPlainTextEdit(QPlainTextEdit):
    """Material Design 1 多行文本框（Text Field Box：6% 浅底 + 底部 1dp/2dp 主色指示线）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._apply_box_style(focused=False)

    def _apply_box_style(self, focused: bool) -> None:
        line_px = 2 if focused else 1
        line_color = PRIMARY_500 if focused else INPUT_LINE_IDLE
        self.setStyleSheet(
            f"MdPlainTextEdit {{"
            f" background-color: #FAFAFA;"
            f" color: {TEXT_PRIMARY};"
            f" border-top: 1px solid {DIVIDER};"
            f" border-left: 1px solid {DIVIDER};"
            f" border-right: 1px solid {DIVIDER};"
            f" border-bottom: {line_px}px solid {line_color};"
            f" border-top-left-radius: 2px;"
            f" border-top-right-radius: 2px;"
            f" padding: 6px 8px;"
            f" selection-background-color: {PRIMARY_200};"
            f" selection-color: {TEXT_PRIMARY};"
            f"}}"
        )

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._apply_box_style(focused=True)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._apply_box_style(focused=False)


class MdCheckBox(QCheckBox):
    """Material Design 1 复选框（18x18dp 2dp 圆角方框，选中填充 #3388BB + 白色矢量对勾）。"""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(28)

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        w = 26 + fm.horizontalAdvance(self.text()) + 8
        return QSize(w, max(28, fm.height() + 8))

    def hitButton(self, pos: QPoint) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        enabled = self.isEnabled()
        checked = self.isChecked()
        box_size = 18.0
        y_box = (self.height() - box_size) / 2.0
        box_rect = QRectF(2.0, y_box, box_size, box_size)

        box_path = QPainterPath()
        box_path.addRoundedRect(box_rect, CORNER_RADIUS, CORNER_RADIUS)

        if checked:
            fill = QColor(PRIMARY_500) if enabled else QColor(INPUT_LINE_DISABLED)
            painter.fillPath(box_path, fill)
            # 绘制白色对勾
            check_pen = QPen(QColor("#FFFFFF"), 2.0)
            check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(check_pen)
            p1 = QPointF(box_rect.left() + 4.0, box_rect.top() + 9.5)
            p2 = QPointF(box_rect.left() + 7.5, box_rect.top() + 13.0)
            p3 = QPointF(box_rect.left() + 14.2, box_rect.top() + 5.5)
            painter.drawLine(p1, p2)
            painter.drawLine(p2, p3)
        else:
            border_color = (
                QColor(TEXT_SECONDARY) if enabled else QColor(INPUT_LINE_DISABLED)
            )
            painter.setPen(QPen(border_color, 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                box_rect.adjusted(1.0, 1.0, -1.0, -1.0),
                CORNER_RADIUS,
                CORNER_RADIUS,
            )

        # 绘制文本
        text_color = QColor(TEXT_PRIMARY) if enabled else QColor(TEXT_DISABLED)
        painter.setPen(text_color)
        text_rect = QRectF(26.0, 0.0, float(self.width() - 26), float(self.height()))
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self.text(),
        )


class MdComboBox(QComboBox):
    """Material Design 1 下拉选择框（底部单横线 + 右侧实心下拉三角）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hovered = False
        self.setMinimumHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        enabled = self.isEnabled()
        focused = self.hasFocus()

        # 1. 绘制当前选中文本
        text_color = QColor(TEXT_PRIMARY) if enabled else QColor(TEXT_DISABLED)
        painter.setPen(text_color)
        text_rect = QRectF(2.0, 0.0, w - 24.0, h - 4.0)
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self.currentText(),
        )

        # 2. 绘制右侧 MD1 倒三角图标 (10x5)
        arrow_color = (
            QColor(PRIMARY_500)
            if (enabled and focused)
            else (QColor(TEXT_SECONDARY) if enabled else QColor(INPUT_LINE_DISABLED))
        )
        cx = w - 10.0
        cy = (h - 4.0) / 2.0
        triangle = QPolygonF(
            [
                QPointF(cx - 4.5, cy - 2.0),
                QPointF(cx + 4.5, cy - 2.0),
                QPointF(cx, cy + 3.0),
            ]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(arrow_color)
        painter.drawPolygon(triangle)

        # 3. 绘制底部单横线
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if not enabled:
            painter.setPen(QPen(QColor(INPUT_LINE_DISABLED), 1.0, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(0.0, h - 1.0), QPointF(w, h - 1.0))
        elif focused:
            painter.fillRect(QRectF(0.0, h - 2.0, w, 2.0), QColor(PRIMARY_500))
        elif self._hovered:
            painter.fillRect(QRectF(0.0, h - 2.0, w, 2.0), QColor(TEXT_PRIMARY))
        else:
            painter.fillRect(QRectF(0.0, h - 1.0, w, 1.0), QColor(INPUT_LINE_IDLE))


def _init_md_spinbox(spin: QSpinBox | QDoubleSpinBox) -> None:
    spin.setFrame(False)
    spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    spin.setMinimumHeight(34)
    spin.setMinimumWidth(90)
    spin.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    line_edit = spin.lineEdit()
    if line_edit is not None:
        line_edit.setFrame(False)
        line_edit.setStyleSheet(
            f"QLineEdit {{"
            f" background: transparent;"
            f" color: {TEXT_PRIMARY};"
            f" border: none;"
            f" selection-background-color: {PRIMARY_200};"
            f" selection-color: {TEXT_PRIMARY};"
            f"}}"
            f"QLineEdit:disabled {{"
            f" color: {TEXT_DISABLED};"
            f"}}"
        )


def _layout_spinbox_editor(spin: QSpinBox | QDoubleSpinBox) -> None:
    line_edit = spin.lineEdit()
    if line_edit is not None:
        line_edit.setGeometry(
            2,
            2,
            max(20, spin.width() - 24),
            max(18, spin.height() - 6),
        )


def _paint_md_spinbox(
    spin: QSpinBox | QDoubleSpinBox, hovered: bool, hover_part: str | None
) -> None:
    painter = QPainter(spin)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    w = float(spin.width())
    h = float(spin.height())
    enabled = spin.isEnabled()
    focused = spin.hasFocus()

    # 1. 绘制右侧上下微调矢量三角 (▴ / ▾)
    cx = w - 10.0
    cy = (h - 4.0) / 2.0
    base_arrow = QColor(TEXT_SECONDARY) if enabled else QColor(INPUT_LINE_DISABLED)
    up_color = (
        QColor(PRIMARY_500)
        if (enabled and (hover_part == "up" or focused))
        else base_arrow
    )
    down_color = (
        QColor(PRIMARY_500)
        if (enabled and (hover_part == "down" or focused))
        else base_arrow
    )

    up_tri = QPolygonF(
        [
            QPointF(cx - 4.0, cy - 1.5),
            QPointF(cx + 4.0, cy - 1.5),
            QPointF(cx, cy - 6.0),
        ]
    )
    down_tri = QPolygonF(
        [
            QPointF(cx - 4.0, cy + 2.5),
            QPointF(cx + 4.0, cy + 2.5),
            QPointF(cx, cy + 7.0),
        ]
    )
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(up_color)
    painter.drawPolygon(up_tri)
    painter.setBrush(down_color)
    painter.drawPolygon(down_tri)

    # 2. 绘制底部 MD1 单横线
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    if not enabled:
        painter.setPen(QPen(QColor(INPUT_LINE_DISABLED), 1.0, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(0.0, h - 1.0), QPointF(w, h - 1.0))
    elif focused:
        painter.fillRect(QRectF(0.0, h - 2.0, w, 2.0), QColor(PRIMARY_500))
    elif hovered:
        painter.fillRect(QRectF(0.0, h - 2.0, w, 2.0), QColor(TEXT_PRIMARY))
    else:
        painter.fillRect(QRectF(0.0, h - 1.0, w, 1.0), QColor(INPUT_LINE_IDLE))


def _spinbox_hit_part(spin: QWidget, pos: QPointF) -> str | None:
    if pos.x() >= spin.width() - 22:
        return "up" if pos.y() < (spin.height() - 2) / 2.0 else "down"
    return None


class MdSpinBox(QSpinBox):
    """Material Design 1 整数微调框（底部单横线 + 矢量上下三角）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hovered = False
        self._hover_part: str | None = None
        _init_md_spinbox(self)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._hover_part = None
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event) -> None:
        self._hover_part = _spinbox_hit_part(self, event.position())
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            part = _spinbox_hit_part(self, event.position())
            if part == "up":
                self.stepUp()
                event.accept()
                return
            if part == "down":
                self.stepDown()
                event.accept()
                return
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        _layout_spinbox_editor(self)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _layout_spinbox_editor(self)

    def paintEvent(self, event) -> None:
        _layout_spinbox_editor(self)
        super().paintEvent(event)
        _paint_md_spinbox(self, self._hovered, self._hover_part)


class MdDoubleSpinBox(QDoubleSpinBox):
    """Material Design 1 浮点数微调框（底部单横线 + 矢量上下三角）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hovered = False
        self._hover_part: str | None = None
        _init_md_spinbox(self)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._hover_part = None
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event) -> None:
        self._hover_part = _spinbox_hit_part(self, event.position())
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            part = _spinbox_hit_part(self, event.position())
            if part == "up":
                self.stepUp()
                event.accept()
                return
            if part == "down":
                self.stepDown()
                event.accept()
                return
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        _layout_spinbox_editor(self)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _layout_spinbox_editor(self)

    def paintEvent(self, event) -> None:
        _layout_spinbox_editor(self)
        super().paintEvent(event)
        _paint_md_spinbox(self, self._hovered, self._hover_part)


class MdProgressBar(QProgressBar):
    """Material Design 1 线性进度指示器（4dp 高，底轨 #C2DDF0，填充 #3388BB）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTextVisible(False)
        self.setFixedHeight(4)
        self.setRange(0, 100)
        self.setValue(0)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        rect = QRectF(self.rect())
        # 1. 底轨 Primary 100
        painter.fillRect(rect, QColor(PRIMARY_100))

        # 2. 进度填充 Primary 500
        minimum = self.minimum()
        maximum = self.maximum()
        span = maximum - minimum
        if span > 0:
            ratio = max(0.0, min(1.0, (self.value() - minimum) / span))
            if ratio > 0.0:
                fill_rect = QRectF(rect.left(), rect.top(), rect.width() * ratio, rect.height())
                painter.fillRect(fill_rect, QColor(PRIMARY_500))


class MdCard(QFrame):
    """Material Design 1 Paper 卡片容器（纯白 #FFFFFF + 2dp 圆角 + 2dp Z-depth 投影）。"""

    def __init__(
        self,
        title: str | None = None,
        parent: QWidget | None = None,
        *,
        elevation: int = 2,
        padding: tuple[int, int, int, int] = (20, 16, 20, 16),
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MdCard")
        self.setStyleSheet(
            f"QFrame#MdCard {{"
            f" background-color: {SURFACE_CARD};"
            f" border-radius: 2px;"
            f" border: none;"
            f"}}"
        )
        if elevation > 0:
            apply_elevation(self, dp=elevation)

        self.body_layout = QVBoxLayout(self)
        self.body_layout.setContentsMargins(*padding)
        self.body_layout.setSpacing(12)

        self.title_label: QLabel | None = None
        if title:
            self.title_label = QLabel(title)
            self.title_label.setStyleSheet(
                f"color: {PRIMARY_500}; font-size: 13px; font-weight: 600;"
            )
            self.body_layout.addWidget(self.title_label)


class MdAppBar(QFrame):
    """Material Design 1 顶部应用栏（4dp Primary 700 状态装饰带 + 52dp Primary 500 栏 + 4dp 阴影）。"""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MdAppBar")
        self.setFixedHeight(APPBAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"QFrame#MdAppBar {{"
            f" background-color: {PRIMARY_500};"
            f" border-top: 4px solid {PRIMARY_700};"
            f" border-bottom: none;"
            f"}}"
        )
        apply_elevation(self, dp=4, color=QColor(0, 0, 0, 60))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 16, 0)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            f"color: {TEXT_ON_PRIMARY}; font-size: 18px; font-weight: 600;"
            " background: transparent;"
        )
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        self._actions_layout = QHBoxLayout()
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(4)
        layout.addLayout(self._actions_layout)

    def add_action_widget(self, widget: QWidget) -> None:
        self._actions_layout.addWidget(widget)


def style_dialog_button_box(
    button_box: QDialogButtonBox,
    *,
    ok_text: str = "确定",
    cancel_text: str = "取消",
) -> None:
    """将 QDialogButtonBox 中的标准按钮替换为 MD1 Flat Buttons（右对齐，取消在左、确定在右）。"""
    ok_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
    cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
    if ok_btn is not None:
        ok_btn.setText(ok_text)
        ok_btn.setMinimumHeight(BUTTON_HEIGHT)
        ok_btn.setMinimumWidth(72)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet(
            f"QPushButton {{"
            f" background-color: transparent;"
            f" color: {PRIMARY_500};"
            f" border: none;"
            f" border-radius: 2px;"
            f" font-weight: 600;"
            f" padding: 0px 16px;"
            f"}}"
            f"QPushButton:hover {{"
            f" background-color: rgba(51, 136, 187, 20);"
            f"}}"
            f"QPushButton:pressed {{"
            f" background-color: rgba(51, 136, 187, 40);"
            f"}}"
        )
    if cancel_btn is not None:
        cancel_btn.setText(cancel_text)
        cancel_btn.setMinimumHeight(BUTTON_HEIGHT)
        cancel_btn.setMinimumWidth(72)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"QPushButton {{"
            f" background-color: transparent;"
            f" color: {TEXT_SECONDARY};"
            f" border: none;"
            f" border-radius: 2px;"
            f" font-weight: 600;"
            f" padding: 0px 16px;"
            f"}}"
            f"QPushButton:hover {{"
            f" background-color: rgba(0, 0, 0, 15);"
            f"}}"
            f"QPushButton:pressed {{"
            f" background-color: rgba(0, 0, 0, 30);"
            f"}}"
        )
