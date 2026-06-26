import sys
import os
import yt_dlp
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QFileDialog, QVBoxLayout, QMenu, QInputDialog, QLineEdit, QSlider, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, QUrl, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve, QEvent
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QBrush, QAction, QIcon, QImage, QPen, QMovie
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink

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
        self.seek_slider = None
        self.change_link_btn = None
        self.resizing = False
        self.resize_edges = []
        self.start_geometry = QRect()
        self.start_mouse_pos = QPoint()
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
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(20)
        self.volume_slider.setGeometry(self.width() - 40, self.height() - 35, 20, 15)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #999;
                height: 4px;
                background: rgba(0, 0, 0, 150);
                margin: 0px 0;
            }
            QSlider::handle:horizontal {
                background: white;
                border: 1px solid #5c5c5c;
                width: 10px;
                margin: -4px 0;
                border-radius: 3px;
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
                background-color: rgba(0, 0, 0, 150);
                color: white;
                border: 1px solid rgba(255, 255, 255, 100);
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(0, 122, 204, 200);
                border: 1px solid rgba(255, 255, 255, 180);
            }
        """)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.hide()
        self.is_paused = False

        # Change link button at top left
        self.change_link_btn = QPushButton("🔗", self)
        self.change_link_btn.setFixedSize(32, 32)
        self.change_link_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 150);
                color: white;
                border: 1px solid rgba(255, 255, 255, 100);
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(0, 122, 204, 200);
                border: 1px solid rgba(255, 255, 255, 180);
            }
        """)
        self.change_link_btn.clicked.connect(self.inputYouTubeLink)
        self.change_link_btn.hide()

        # Seek segmented slider
        self.seek_slider = SegmentedProgressBar(self)
        self.seek_slider.seek_requested.connect(self.on_seek_requested)
        self.seek_slider.hide()
        
        self.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'volume_slider'):
            self.volume_slider.move(self.width() - self.volume_slider.width() - 20, self.height() - self.volume_slider.height() - 20)
        if hasattr(self, 'pause_btn'):
            self.pause_btn.move(20, self.height() - self.pause_btn.height() - 20)
        if hasattr(self, 'change_link_btn') and self.change_link_btn:
            self.change_link_btn.move(20, 20)
        if hasattr(self, 'seek_slider') and self.seek_slider:
            self.seek_slider.setGeometry(20, self.height() - 88, self.width() - 40, 35)

    def eventFilter(self, obj, event):
        if obj == self.volume_slider:
            if event.type() == QEvent.Type.Enter:
                self.volume_anim = QPropertyAnimation(self.volume_slider, b"geometry")
                self.volume_anim.setDuration(200)
                end_rect = QRect(self.width() - 80 - 20, self.height() - 15 - 20, 80, 15)
                self.volume_anim.setEndValue(end_rect)
                self.volume_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
                self.volume_anim.start()
            elif event.type() == QEvent.Type.Leave:
                self.volume_anim = QPropertyAnimation(self.volume_slider, b"geometry")
                self.volume_anim.setDuration(200)
                end_rect = QRect(self.width() - 20 - 20, self.height() - 15 - 20, 20, 15)
                self.volume_anim.setEndValue(end_rect)
                self.volume_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
                self.volume_anim.start()
        return super().eventFilter(obj, event)

    def on_volume_changed(self, value):
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
            # Scale pixmap to fit the widget exactly
            scaled_pixmap = self.pixmap.scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            painter.drawPixmap(0, 0, scaled_pixmap)
            
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

    def process_link(self, url):
        self.label.setText("Đang tải...\nVui lòng đợi")
        self.label.show()
        if hasattr(self, 'link_input'):
            self.link_input.hide()
        if hasattr(self, 'volume_slider'):
            self.volume_slider.hide()
        if hasattr(self, 'seek_slider') and self.seek_slider:
            self.seek_slider.hide()
        if hasattr(self, 'change_link_btn') and self.change_link_btn:
            self.change_link_btn.hide()
        self.update()
        
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
        
        if hasattr(self, 'volume_slider'):
            self.volume_slider.hide()
            
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
            if hasattr(self, 'volume_slider'):
                self.volume_slider.show()
            if hasattr(self, 'pause_btn'):
                self.pause_btn.show()
            if hasattr(self, 'seek_slider') and self.seek_slider:
                self.seek_slider.show()
            if hasattr(self, 'change_link_btn') and self.change_link_btn:
                self.change_link_btn.show()
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
            
            if hasattr(self, 'volume_slider'):
                self.volume_slider.show()
            if hasattr(self, 'pause_btn'):
                self.pause_btn.show()
            if hasattr(self, 'seek_slider') and self.seek_slider:
                self.seek_slider.show()
            if hasattr(self, 'change_link_btn') and self.change_link_btn:
                self.change_link_btn.show()
            
        else:
            self.pixmap = QPixmap(path)
            self.update() # Trigger paintEvent
            
        self.label.hide() # Hide text
        if hasattr(self, 'link_input'):
            self.link_input.hide()
        # Ẩn nút pause nếu không phải video
        if not self.media_player and hasattr(self, 'pause_btn'):
            self.pause_btn.hide()
        
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
