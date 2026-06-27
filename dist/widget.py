import sys
import os
import yt_dlp
import re
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QFileDialog, QVBoxLayout, QMenu, QInputDialog, QLineEdit, QSlider, QPushButton, QHBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, QUrl, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve, QEvent, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QBrush, QAction, QIcon, QImage, QPen, QMovie, QCursor
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink
from PyQt6.QtWebEngineWidgets import QWebEngineView

class YouTubeFetcher(QThread):
    finished = pyqtSignal(str, dict)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                stream_url = info.get('url', None)
                if stream_url:
                    self.finished.emit(stream_url, info)
                else:
                    self.error.emit("Không lấy được link stream.")
        except Exception as e:
            self.error.emit(str(e))

def format_time(ms):
    s = ms // 1000
    m = s // 60
    h = m // 60
    s = s % 60
    m = m % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"

class SegmentedProgressBar(QWidget):
    seek_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 0
        self.position = 0
        self.chapters = []
        self.is_hovering = False
        self.is_dragging = False
        self.hover_pos = QPoint()
        self.setMouseTracking(True)
        self.setFixedHeight(35)

    def setDuration(self, duration):
        if duration != self.duration:
            self.duration = duration
            self.update()

    def setPosition(self, position):
        if position != self.position:
            self.position = position
            self.update()

    def setChapters(self, chapters):
        self.chapters = chapters
        self.update()

    def _get_segments(self):
        if self.duration <= 0:
            return []
        if self.chapters:
            return self.chapters
        
        # Default to 5 segments
        segments = []
        seg_dur = self.duration / 5
        for i in range(5):
            segments.append({
                'start': int(i * seg_dur),
                'end': int((i + 1) * seg_dur),
                'title': f"Đoạn {i + 1}"
            })
        return segments

    def _get_segments_layout(self):
        segments = self._get_segments()
        if not segments:
            return []
        total_w = self.width()
        gap = 3
        n = len(segments)
        avail_w = total_w - (n - 1) * gap
        
        layout = []
        for i, seg in enumerate(segments):
            frac_start = seg['start'] / self.duration if self.duration > 0 else 0
            frac_end = seg['end'] / self.duration if self.duration > 0 else 0
            x_start = int(frac_start * avail_w) + i * gap
            x_end = int(frac_end * avail_w) + i * gap
            layout.append({
                'x_start': x_start,
                'x_end': x_end,
                'w': x_end - x_start,
                'start': seg['start'],
                'end': seg['end'],
                'title': seg['title']
            })
        return layout

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        layout = self._get_segments_layout()
        y_center = 28
        bar_h = 6 if (self.is_hovering or self.is_dragging) else 3
        
        if not layout:
            painter.fillRect(0, y_center - bar_h // 2, self.width(), bar_h, QColor(255, 255, 255, 80))
            return

        pos_x = 0
        for item in layout:
            if item['start'] <= self.position <= item['end']:
                if item['end'] > item['start']:
                    frac = (self.position - item['start']) / (item['end'] - item['start'])
                else:
                    frac = 0
                pos_x = item['x_start'] + int(frac * item['w'])
                break
            elif self.position > item['end']:
                pos_x = item['x_end']

        for item in layout:
            bg_rect = QRect(item['x_start'], y_center - bar_h // 2, item['w'], bar_h)
            painter.fillRect(bg_rect, QColor(255, 255, 255, 80))
            if self.position >= item['end']:
                painter.fillRect(bg_rect, QColor(230, 33, 23))
            elif item['start'] <= self.position <= item['end']:
                played_w = pos_x - item['x_start']
                if played_w > 0:
                    played_rect = QRect(item['x_start'], y_center - bar_h // 2, played_w, bar_h)
                    painter.fillRect(played_rect, QColor(230, 33, 23))

        if self.is_hovering or self.is_dragging:
            painter.setBrush(QBrush(QColor(230, 33, 23)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(pos_x, y_center), 6, 6)

        if self.is_hovering and layout:
            hover_item = None
            hx = self.hover_pos.x()
            for item in layout:
                if item['x_start'] <= hx <= item['x_end']:
                    hover_item = item
                    break
            if not hover_item and layout:
                if hx < layout[0]['x_start']:
                    hover_item = layout[0]
                elif hx > layout[-1]['x_end']:
                    hover_item = layout[-1]
                else:
                    for i in range(len(layout) - 1):
                        if layout[i]['x_end'] <= hx <= layout[i+1]['x_start']:
                            if hx - layout[i]['x_end'] < layout[i+1]['x_start'] - hx:
                                hover_item = layout[i]
                            else:
                                hover_item = layout[i+1]
                            break
            if hover_item:
                if hx <= hover_item['x_start']:
                    hover_time = hover_item['start']
                elif hx >= hover_item['x_end']:
                    hover_time = hover_item['end']
                else:
                    if hover_item['w'] > 0:
                        frac = (hx - hover_item['x_start']) / hover_item['w']
                    else:
                        frac = 0
                    hover_time = int(hover_item['start'] + frac * (hover_item['end'] - hover_item['start']))
                
                time_str = format_time(hover_time)
                text = f"{hover_item['title']} - {time_str}"
                
                font = painter.font()
                font.setPointSize(9)
                painter.setFont(font)
                metrics = painter.fontMetrics()
                text_w = metrics.horizontalAdvance(text)
                text_h = metrics.height()
                
                tooltip_w = text_w + 16
                tooltip_h = text_h + 8
                
                tooltip_x = hx - tooltip_w // 2
                tooltip_x = max(2, min(tooltip_x, self.width() - tooltip_w - 2))
                tooltip_y = 0
                
                painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
                painter.setBrush(QBrush(QColor(0, 0, 0, 200)))
                painter.drawRoundedRect(QRect(tooltip_x, tooltip_y, tooltip_w, tooltip_h), 4, 4)
                
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(QRect(tooltip_x, tooltip_y, tooltip_w, tooltip_h), Qt.AlignmentFlag.AlignCenter, text)

    def _get_time_for_x(self, x):
        layout = self._get_segments_layout()
        if not layout:
            return 0
        x = max(layout[0]['x_start'], min(x, layout[-1]['x_end']))
        for item in layout:
            if item['x_start'] <= x <= item['x_end']:
                if item['w'] > 0:
                    frac = (x - item['x_start']) / item['w']
                else:
                    frac = 0
                return int(item['start'] + frac * (item['end'] - item['start']))
            elif x < item['x_start']:
                return item['start']
        return self.duration

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            time_ms = self._get_time_for_x(event.position().x())
            self.seek_requested.emit(time_ms)
            self.update()

    def mouseMoveEvent(self, event):
        self.hover_pos = event.position().toPoint()
        if self.is_dragging:
            time_ms = self._get_time_for_x(event.position().x())
            self.seek_requested.emit(time_ms)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.update()

    def enterEvent(self, event):
        self.is_hovering = True
        self.update()

    def leaveEvent(self, event):
        self.is_hovering = False
        self.update()

class ImageWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.dragPos = QPoint()
        self.image_path = None
        self.pixmap = None
        self.movie = None
        self.media_player = None
        self.audio_output = None
        self.video_sink = None
        self.yt_fetcher = None
        self.web_view = None
        self.seek_slider = None
        self.change_link_btn = None
        self.resizing = False
        self.resize_edges = []
        self.start_geometry = QRect()
        self.start_mouse_pos = QPoint()
        self.is_hovered = False
        self.control_anims = []
        self.initUI()

    def initUI(self):
        # Set window flags for frameless, always on top, and hide from taskbar (Tool)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Enable mouse tracking for resize cursors
        self.setMouseTracking(True)
        
        # Initial size
        self.resize(300, 300)
        self.setMinimumSize(100, 100)
        self.setAcceptDrops(True)
        
        # Layout and Label
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.label = QLabel("Click đúp\nhoặc\nKéo thả ảnh/video\nvào đây", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: white; font-weight: bold; font-family: 'Segoe UI', sans-serif; font-size: 16px;")
        self.layout.addWidget(self.label)
        
        self.link_input = QLineEdit(self)
        self.link_input.setPlaceholderText("Dán link FB/YouTube (Enter)")
        self.link_input.setStyleSheet("background-color: rgba(255, 255, 255, 50); color: white; border: 1px solid white; border-radius: 5px; padding: 5px;")
        self.link_input.returnPressed.connect(self.on_link_entered)
        self.layout.addWidget(self.link_input)
        
        # Volume button
        self.volume_btn = QPushButton("🔊", self)
        self.volume_btn.setFixedSize(32, 32)
        self.volume_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                font-size: 18px;
            }
            QPushButton:hover {
                color: #ff3333;
            }
        """)
        self.volume_btn.hide()
        self.volume_btn.installEventFilter(self)
        self.volume_btn.clicked.connect(self.toggle_mute)
        self.is_muted = False
        self.last_volume = 20

        self.volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(20)
        self.volume_slider.setFixedSize(0, 15)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 60);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: white;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 12px;
                height: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #ff3333;
            }
        """)
        self.volume_slider.hide()
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        self.volume_slider.installEventFilter(self)
        self.volume_anim = None
        
        # Pause/Play button
        self.pause_btn = QPushButton("⏸", self)
        self.pause_btn.setFixedSize(32, 32)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                font-size: 18px;
            }
            QPushButton:hover {
                color: #ff3333;
            }
        """)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.hide()
        self.is_paused = False

        # Rewind button
        self.rewind_btn = QPushButton("⏪", self)
        self.rewind_btn.setFixedSize(32, 32)
        self.rewind_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                color: #ff3333;
            }
        """)
        self.rewind_btn.clicked.connect(self.skip_backward)
        self.rewind_btn.hide()

        # Forward button
        self.forward_btn = QPushButton("⏩", self)
        self.forward_btn.setFixedSize(32, 32)
        self.forward_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                color: #ff3333;
            }
        """)
        self.forward_btn.clicked.connect(self.skip_forward)
        self.forward_btn.hide()

        # Change link button at top left
        self.change_link_btn = QPushButton("🔗", self)
        self.change_link_btn.setFixedSize(32, 32)
        self.change_link_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(20, 20, 20, 200);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(230, 33, 23, 220);
                border: 1px solid rgba(255, 255, 255, 80);
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: rgba(180, 20, 15, 240);
            }
        """)
        self.change_link_btn.clicked.connect(self.inputYouTubeLink)
        self.change_link_btn.hide()

        # Seek segmented slider
        self.seek_slider = SegmentedProgressBar(self)
        self.seek_slider.seek_requested.connect(self.on_seek_requested)
        self.seek_slider.hide()
        
        # WebEngineView for YouTube
        self.web_view = QWebEngineView(self)
        self.web_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.web_view.hide()
        
        self.hover_timer = QTimer(self)
        self.hover_timer.setInterval(200)
        self.hover_timer.timeout.connect(self._timer_check_hover)
        self.hover_timer.start()
        
        self.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'web_view') and self.web_view:
            # Leave a 10px margin so the user can drag/resize the widget from the edges
            self.web_view.setGeometry(10, 10, self.width() - 20, self.height() - 20)
        
        # Align YouTube-like controls at bottom left
        y_pos = self.height() - 40
        if hasattr(self, 'pause_btn'):
            self.pause_btn.move(15, y_pos)
        if hasattr(self, 'rewind_btn'):
            self.rewind_btn.move(45, y_pos)
        if hasattr(self, 'forward_btn'):
            self.forward_btn.move(75, y_pos)
        if hasattr(self, 'volume_btn'):
            self.volume_btn.move(105, y_pos)
        if hasattr(self, 'volume_slider'):
            self.volume_slider.move(140, y_pos + 8) # Offset to align vertically with buttons

        if hasattr(self, 'change_link_btn') and self.change_link_btn:
            self.change_link_btn.move(20, 20)
        if hasattr(self, 'seek_slider') and self.seek_slider:
            self.seek_slider.setGeometry(20, self.height() - 88, self.width() - 40, 35)

    def eventFilter(self, obj, event):
        if obj in (self.volume_btn, self.volume_slider):
            if event.type() == QEvent.Type.Enter:
                self._expand_volume()
            elif event.type() == QEvent.Type.Leave:
                QTimer.singleShot(50, self._check_collapse_volume)
        return super().eventFilter(obj, event)

    def _expand_volume(self):
        self.volume_slider.show()
        if not hasattr(self, 'vol_anim') or self.vol_anim.state() != QPropertyAnimation.State.Running:
            self.vol_anim = QPropertyAnimation(self.volume_slider, b"minimumWidth")
            self.vol_anim.setDuration(150)
            self.vol_anim.setEndValue(60)
            self.vol_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            
            self.vol_anim2 = QPropertyAnimation(self.volume_slider, b"maximumWidth")
            self.vol_anim2.setDuration(150)
            self.vol_anim2.setEndValue(60)
            self.vol_anim2.setEasingCurve(QEasingCurve.Type.OutQuad)
            
            self.vol_anim.start()
            self.vol_anim2.start()

    def _check_collapse_volume(self):
        pos = QCursor.pos()
        vol_btn_rect = QRect(self.volume_btn.mapToGlobal(QPoint(0,0)), self.volume_btn.size())
        vol_slider_rect = QRect(self.volume_slider.mapToGlobal(QPoint(0,0)), self.volume_slider.size())
        
        # Add a tiny padding to prevent flickering
        vol_slider_rect.adjust(-5, -5, 5, 5)
        
        if not (vol_btn_rect.contains(pos) or vol_slider_rect.contains(pos)):
            self.vol_anim = QPropertyAnimation(self.volume_slider, b"minimumWidth")
            self.vol_anim.setDuration(150)
            self.vol_anim.setEndValue(0)
            self.vol_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            
            self.vol_anim2 = QPropertyAnimation(self.volume_slider, b"maximumWidth")
            self.vol_anim2.setDuration(150)
            self.vol_anim2.setEndValue(0)
            self.vol_anim2.setEasingCurve(QEasingCurve.Type.OutQuad)
            
            def hide_slider():
                if self.volume_slider.width() == 0:
                    self.volume_slider.hide()
            self.vol_anim.finished.connect(hide_slider)
            
            self.vol_anim.start()
            self.vol_anim2.start()

    def toggle_mute(self):
        if self.is_muted:
            self.is_muted = False
            self.volume_slider.setValue(self.last_volume)
            self.volume_btn.setText("🔊")
            if self.audio_output:
                self.audio_output.setVolume(self.last_volume / 100.0)
        else:
            self.is_muted = True
            self.last_volume = self.volume_slider.value() if self.volume_slider.value() > 0 else 20
            self.volume_slider.setValue(0)
            self.volume_btn.setText("🔇")
            if self.audio_output:
                self.audio_output.setVolume(0.0)

    def on_volume_changed(self, value):
        if value > 0 and self.is_muted:
            self.is_muted = False
        
        if value == 0:
            self.volume_btn.setText("🔇")
        elif value < 50:
            self.volume_btn.setText("🔉")
        else:
            self.volume_btn.setText("🔊")
            
        if self.audio_output:
            self.audio_output.setVolume(value / 100.0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        rect = self.rect()
        path = QPainterPath()
        # Radius of 15 for rounded corners
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 15, 15)
        
        # Clip painter to rounded path
        painter.setClipPath(path)
        
        if self.pixmap:
            # Scale pixmap preserving aspect ratio
            scaled_pixmap = self.pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            
            x = (self.width() - scaled_pixmap.width()) // 2
            y = (self.height() - scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, scaled_pixmap)
            
            # Add a 5px thin border around the image
            pen = QPen(QColor(255, 255, 255, 200)) # Semi-transparent white border
            pen.setWidth(5)
            painter.setPen(pen)
            
            # Adjust rect slightly inward so the 5px border is not clipped by the widget path
            border_rect = rect.adjusted(2, 2, -2, -2)
            border_path = QPainterPath()
            border_path.addRoundedRect(border_rect.x(), border_rect.y(), border_rect.width(), border_rect.height(), 15, 15)
            painter.drawPath(border_path)
        else:
            # Default background (Glassmorphism-like)
            painter.fillPath(path, QColor(40, 44, 52, 200)) # Semi-transparent dark background
            # Add a subtle border
            painter.setPen(QColor(255, 255, 255, 30))
            painter.drawPath(path)
            
    def _get_resize_edges(self, pos):
        margin = 15
        rect = self.rect()
        edges = []
        if pos.x() < margin:
            edges.append('left')
        elif pos.x() > rect.width() - margin:
            edges.append('right')
        if pos.y() < margin:
            edges.append('top')
        elif pos.y() > rect.height() - margin:
            edges.append('bottom')
        return edges

    def _update_cursor(self, edges):
        if ('left' in edges and 'top' in edges) or ('right' in edges and 'bottom' in edges):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif ('right' in edges and 'top' in edges) or ('left' in edges and 'bottom' in edges):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif 'left' in edges or 'right' in edges:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif 'top' in edges or 'bottom' in edges:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self._get_resize_edges(event.position().toPoint())
            if edges:
                self.resizing = True
                self.resize_edges = edges
                self.start_geometry = self.geometry()
                self.start_mouse_pos = event.globalPosition().toPoint()
            else:
                self.resizing = False
                self.dragPos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.showContextMenu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.NoButton:
            edges = self._get_resize_edges(event.position().toPoint())
            self._update_cursor(edges)
        elif event.buttons() == Qt.MouseButton.LeftButton:
            if getattr(self, 'resizing', False):
                dx = event.globalPosition().toPoint().x() - self.start_mouse_pos.x()
                dy = event.globalPosition().toPoint().y() - self.start_mouse_pos.y()
                
                x, y, w, h = self.start_geometry.getRect()
                min_w = self.minimumWidth()
                min_h = self.minimumHeight()
                
                if 'left' in self.resize_edges:
                    if w - dx >= min_w:
                        x += dx
                        w -= dx
                    else:
                        dx = w - min_w
                        x += dx
                        w = min_w
                elif 'right' in self.resize_edges:
                    if w + dx >= min_w:
                        w += dx
                    else:
                        w = min_w
                        
                if 'top' in self.resize_edges:
                    if h - dy >= min_h:
                        y += dy
                        h -= dy
                    else:
                        dy = h - min_h
                        y += dy
                        h = min_h
                elif 'bottom' in self.resize_edges:
                    if h + dy >= min_h:
                        h += dy
                    else:
                        h = min_h
                        
                self.setGeometry(x, y, w, h)
                self.update()
            else:
                if hasattr(self, 'dragPos'):
                    self.move(event.globalPosition().toPoint() - self.dragPos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.resizing = False
            self.resize_edges = []
            self._update_cursor(self._get_resize_edges(event.position().toPoint()))
            
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Chỉ cho phép chọn ảnh khi KHÔNG đang ở trạng thái video
            if self.media_player is None:
                self.selectImage()

    def enterEvent(self, event):
        self.check_hover_and_update(duration=250, force=False)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.check_hover_and_update(duration=250, force=False)
        super().leaveEvent(event)

    def _timer_check_hover(self):
        self.check_hover_and_update(duration=250, force=False)

    def check_hover_and_update(self, duration=0, force=True):
        pos = QCursor.pos()
        is_inside = self.rect().contains(self.mapFromGlobal(pos))
        
        is_dragging = False
        if hasattr(self, 'seek_slider') and getattr(self.seek_slider, 'is_dragging', False):
            is_dragging = True
            
        if is_inside:
            if not self.is_hovered or force:
                self.is_hovered = True
                self.fade_controls(True, duration=duration)
        else:
            if (self.is_hovered and not is_dragging) or force:
                self.is_hovered = False
                self.fade_controls(False, duration=duration)

    def fade_controls(self, show, duration=250):
        has_video = self.media_player is not None
        is_youtube = hasattr(self, 'web_view') and self.web_view.isVisible()
        
        # Stop any existing animations
        if hasattr(self, 'control_anims') and self.control_anims:
            for anim in self.control_anims:
                anim.stop()
        self.control_anims = []

        controls = []
        if hasattr(self, 'pause_btn') and self.pause_btn:
            controls.append((self.pause_btn, has_video))
        if hasattr(self, 'rewind_btn') and self.rewind_btn:
            controls.append((self.rewind_btn, has_video))
        if hasattr(self, 'forward_btn') and self.forward_btn:
            controls.append((self.forward_btn, has_video))
        if hasattr(self, 'volume_btn') and self.volume_btn:
            controls.append((self.volume_btn, has_video))
        if hasattr(self, 'seek_slider') and self.seek_slider:
            controls.append((self.seek_slider, has_video))
        if hasattr(self, 'change_link_btn') and self.change_link_btn:
            controls.append((self.change_link_btn, has_video or is_youtube))

        for widget, condition in controls:
            should_show = condition and show
            target_opacity = 1.0 if should_show else 0.0
            
            effect = widget.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(effect)
            
            if duration == 0:
                effect.setOpacity(target_opacity)
                widget.setVisible(should_show)
                widget.setEnabled(should_show)
            else:
                if should_show:
                    widget.show()
                    widget.setEnabled(True)
                else:
                    widget.setEnabled(False)
                
                anim = QPropertyAnimation(effect, b"opacity")
                anim.setDuration(duration)
                anim.setStartValue(effect.opacity())
                anim.setEndValue(target_opacity)
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                
                if not should_show:
                    def make_hide_callback(w=widget):
                        def callback():
                            eff = w.graphicsEffect()
                            if eff and eff.opacity() == 0.0:
                                w.hide()
                        return callback
                    anim.finished.connect(make_hide_callback())
                    
                anim.start()
                self.control_anims.append(anim)

        if is_youtube:
            if show:
                self.web_view.page().runJavaScript("""
                    var iframe = document.querySelector('iframe');
                    if (iframe) {
                        iframe.style.pointerEvents = 'auto';
                    }
                """)
            else:
                self.web_view.page().runJavaScript("""
                    var iframe = document.querySelector('iframe');
                    if (iframe) {
                        iframe.style.pointerEvents = 'none';
                    }
                """)

    def toggle_pause(self):
        if self.media_player:
            if self.is_paused:
                self.media_player.play()
                self.is_paused = False
                self.pause_btn.setText("⏸")
            else:
                self.media_player.pause()
                self.is_paused = True
                self.pause_btn.setText("▶")

    def skip_forward(self):
        if self.media_player:
            pos = self.media_player.position()
            duration = self.media_player.duration()
            new_pos = min(pos + 10000, duration)
            self.media_player.setPosition(new_pos)

    def skip_backward(self):
        if self.media_player:
            pos = self.media_player.position()
            new_pos = max(pos - 10000, 0)
            self.media_player.setPosition(new_pos)

    def showContextMenu(self, pos):
        contextMenu = QMenu(self)
        contextMenu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #444;
                border-radius: 5px;
            }
            QMenu::item {
                padding: 5px 20px 5px 20px;
            }
            QMenu::item:selected {
                background-color: #007acc;
            }
        """)
        selectAction = contextMenu.addAction("Chọn Media (Ảnh/Video)...")
        youtubeAction = contextMenu.addAction("Nhập link YouTube...")
        resize1Action = contextMenu.addAction("Kích thước: Vuông nhỏ (300x300)")
        resize2Action = contextMenu.addAction("Kích thước: Chữ nhật dọc (300x450)")
        resize3Action = contextMenu.addAction("Kích thước: Chữ nhật ngang (450x300)")
        contextMenu.addSeparator()
        quitAction = contextMenu.addAction("Thoát Widget")
        
        action = contextMenu.exec(pos)
        
        if action == quitAction:
            QApplication.quit()
        elif action == selectAction:
            self.selectImage()
        elif action == youtubeAction:
            self.inputYouTubeLink()
        elif action == resize1Action:
            self.resize(300, 300)
            self.update()
        elif action == resize2Action:
            self.resize(300, 450)
            self.update()
        elif action == resize3Action:
            self.resize(450, 300)
            self.update()

    def selectImage(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Chọn Media", "", "Media Files (*.png *.jpg *.jpeg *.bmp *.gif *.mp4 *.avi *.mkv *.mov *.wmv)")
        if file_name:
            self.loadMedia(file_name)

    def inputYouTubeLink(self):
        url, ok = QInputDialog.getText(self, "Nhập Link", "Nhập link YouTube/Facebook:")
        if ok and url.strip():
            self.process_link(url.strip())

    def on_link_entered(self):
        url = self.link_input.text().strip()
        if url:
            self.process_link(url)

    def on_seek_requested(self, ms):
        if self.media_player:
            self.media_player.setPosition(ms)

    def on_position_changed(self, position):
        if hasattr(self, 'seek_slider') and self.seek_slider:
            if not self.seek_slider.is_dragging:
                self.seek_slider.setPosition(position)

    def on_duration_changed(self, duration):
        if hasattr(self, 'seek_slider') and self.seek_slider:
            self.seek_slider.setDuration(duration)

    def load_webengine_youtube(self, video_id):
        if self.movie:
            self.movie.stop()
            self.movie = None
        if self.media_player:
            self.media_player.stop()
            self.media_player = None
            self.video_sink = None
            self.audio_output = None
        self.pixmap = None
        
        self.label.hide()
        if hasattr(self, 'link_input'):
            self.link_input.hide()
        
        if hasattr(self, 'seek_slider') and self.seek_slider:
            self.seek_slider.hide()
        if hasattr(self, 'pause_btn'):
            self.pause_btn.hide()
        if hasattr(self, 'rewind_btn'):
            self.rewind_btn.hide()
        if hasattr(self, 'forward_btn'):
            self.forward_btn.hide()
        if hasattr(self, 'volume_btn'):
            self.volume_btn.hide()
        if hasattr(self, 'volume_slider'):
            self.volume_slider.hide()
            
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
          body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background-color: transparent; border-radius: 5px; }}
          iframe {{ width: 100%; height: 100%; border: none; border-radius: 5px; }}
        </style>
        </head>
        <body>
          <iframe src="https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0" allow="autoplay; encrypted-media" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>
        </body>
        </html>
        """
        self.web_view.setHtml(html, QUrl("https://localhost/"))
        self.web_view.show()
        
        if hasattr(self, 'change_link_btn') and self.change_link_btn:
            self.change_link_btn.show()
            self.change_link_btn.raise_()
        
        self.update()
        self.check_hover_and_update()

    def process_link(self, url):
        self.label.setText("Đang tải...\nVui lòng đợi")
        self.label.show()
        if hasattr(self, 'link_input'):
            self.link_input.hide()
        if hasattr(self, 'volume_slider'):
            self.volume_slider.hide()
        if hasattr(self, 'volume_btn'):
            self.volume_btn.hide()
        if hasattr(self, 'rewind_btn'):
            self.rewind_btn.hide()
        if hasattr(self, 'forward_btn'):
            self.forward_btn.hide()
        if hasattr(self, 'seek_slider') and self.seek_slider:
            self.seek_slider.hide()
        if hasattr(self, 'change_link_btn') and self.change_link_btn:
            self.change_link_btn.hide()
        self.update()
        
        youtube_regex = r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})"
        match = re.search(youtube_regex, url)
        if match and ('youtube.com' in url.lower() or 'youtu.be' in url.lower()):
            video_id = match.group(1)
            self.load_webengine_youtube(video_id)
            return

        if self.movie:
            self.movie.stop()
            self.movie = None
        if self.media_player:
            self.media_player.stop()
            self.media_player = None
            self.video_sink = None
            self.audio_output = None
        self.pixmap = None
        
        self.yt_fetcher = YouTubeFetcher(url)
        self.yt_fetcher.finished.connect(self.on_youtube_fetched)
        self.yt_fetcher.error.connect(self.on_youtube_error)
        self.yt_fetcher.start()

    def on_youtube_fetched(self, stream_url, info):
        self.loadMedia(stream_url, is_url=True, info=info)

    def on_youtube_error(self, err):
        self.label.setText(f"Lỗi tải link:\n{err[:30]}...")
        self.label.show()
        if hasattr(self, 'link_input'):
            self.link_input.show()
        if hasattr(self, 'change_link_btn') and self.change_link_btn:
            self.change_link_btn.hide()

    def loadMedia(self, path, is_url=False, info=None):
        self.image_path = path
        
        if hasattr(self, 'web_view') and self.web_view:
            self.web_view.hide()
            self.web_view.setHtml("")
            
        if hasattr(self, 'volume_slider'):
            self.volume_slider.hide()
        if hasattr(self, 'volume_btn'):
            self.volume_btn.hide()
        if hasattr(self, 'rewind_btn'):
            self.rewind_btn.hide()
        if hasattr(self, 'forward_btn'):
            self.forward_btn.hide()
            
        # Dọn dẹp media cũ
        if self.movie:
            self.movie.stop()
            self.movie = None
        if self.media_player:
            self.media_player.stop()
            self.media_player = None
            self.video_sink = None
            self.audio_output = None
            
        # Nạp danh sách chương nếu có
        chapters = []
        if info and 'chapters' in info and info['chapters']:
            for ch in info['chapters']:
                chapters.append({
                    'start': int(ch.get('start_time', 0) * 1000),
                    'end': int(ch.get('end_time', 0) * 1000),
                    'title': ch.get('title', 'Đoạn')
                })
        
        if hasattr(self, 'seek_slider') and self.seek_slider:
            self.seek_slider.setChapters(chapters)
            self.seek_slider.setPosition(0)
            self.seek_slider.setDuration(0)

        if is_url:
            self.media_player = QMediaPlayer()
            self.audio_output = QAudioOutput()
            self.media_player.setAudioOutput(self.audio_output)
            
            self.video_sink = QVideoSink()
            self.media_player.setVideoOutput(self.video_sink)
            self.video_sink.videoFrameChanged.connect(self.on_video_frame)
            self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
            self.media_player.positionChanged.connect(self.on_position_changed)
            self.media_player.durationChanged.connect(self.on_duration_changed)
            
            self.media_player.setSource(QUrl(path))
            self.audio_output.setVolume(self.volume_slider.value() / 100.0 if hasattr(self, 'volume_slider') else 1.0)
            self.media_player.play()
            self.is_paused = False
            self.pause_btn.setText("⏸")
            
            self.label.hide()
            if hasattr(self, 'link_input'):
                self.link_input.hide()
            self.check_hover_and_update()
            return
            
        ext = path.lower().split('.')[-1]
        
        if ext == 'gif':
            self.movie = QMovie(path)
            self.movie.frameChanged.connect(self.on_movie_frame)
            self.movie.start()
            
        elif ext in ['mp4', 'avi', 'mkv', 'mov', 'wmv']:
            self.media_player = QMediaPlayer()
            self.audio_output = QAudioOutput()
            self.media_player.setAudioOutput(self.audio_output)
            
            self.video_sink = QVideoSink()
            self.media_player.setVideoOutput(self.video_sink)
            self.video_sink.videoFrameChanged.connect(self.on_video_frame)
            self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
            self.media_player.positionChanged.connect(self.on_position_changed)
            self.media_player.durationChanged.connect(self.on_duration_changed)
            
            self.media_player.setSource(QUrl.fromLocalFile(path))
            self.audio_output.setVolume(self.volume_slider.value() / 100.0 if hasattr(self, 'volume_slider') else 1.0)
            self.media_player.play()
            self.is_paused = False
            self.pause_btn.setText("⏸")
            if hasattr(self, 'rewind_btn'): self.rewind_btn.show()
            if hasattr(self, 'forward_btn'): self.forward_btn.show()
            
            self.check_hover_and_update()
            
        else:
            self.pixmap = QPixmap(path)
            self.update() # Trigger paintEvent
            
        self.label.hide() # Hide text
        if hasattr(self, 'link_input'):
            self.link_input.hide()
        self.check_hover_and_update()
        
    def on_movie_frame(self, frame_number):
        self.pixmap = self.movie.currentPixmap()
        self.update()
        
    def on_video_frame(self, frame):
        if frame.isValid():
            image = frame.toImage()
            self.pixmap = QPixmap.fromImage(image)
            self.update()
            
    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.media_player.setPosition(0)
            self.media_player.play()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.mp4', '.avi', '.mkv', '.mov', '.wmv')):
                self.loadMedia(file_path)
                break

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("Desktop Image Widget v1.1")
    
    widget = ImageWidget()
    
    # We use pythonw.exe to run without a console window usually, 
    # but running from terminal here is fine for testing.
    sys.exit(app.exec())
