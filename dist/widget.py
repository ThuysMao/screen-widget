import sys
import os
import yt_dlp
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QFileDialog, QVBoxLayout, QMenu, QInputDialog
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, QUrl, pyqtSignal, QThread
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QBrush, QAction, QIcon, QImage, QPen, QMovie
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink

class YouTubeFetcher(QThread):
    finished = pyqtSignal(str)
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
                    self.finished.emit(stream_url)
                else:
                    self.error.emit("Không lấy được link stream.")
        except Exception as e:
            self.error.emit(str(e))

class ImageWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.dragPos = QPoint()
        self.image_path = None
        self.pixmap = None
        self.movie = None
        self.media_player = None
        self.audio_output = None
        self.video_sink = None
        self.yt_fetcher = None
        self.resizing = False
        self.resize_edges = []
        self.start_geometry = QRect()
        self.start_mouse_pos = QPoint()

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
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel("Click đúp\nhoặc\nKéo thả ảnh/video\nvào đây", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: white; font-weight: bold; font-family: 'Segoe UI', sans-serif; font-size: 16px;")
        self.layout.addWidget(self.label)
        
        self.show()

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
            self.selectImage()

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
        url, ok = QInputDialog.getText(self, "YouTube", "Nhập link YouTube:")
        if ok and url:
            self.label.setText("Đang tải YouTube...\nVui lòng đợi")
            self.label.show()
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

    def on_youtube_fetched(self, stream_url):
        self.loadMedia(stream_url, is_url=True)

    def on_youtube_error(self, err):
        self.label.setText(f"Lỗi tải YouTube:\n{err[:30]}...")
        self.label.show()

    def loadMedia(self, path, is_url=False):
        self.image_path = path
        
        # Dọn dẹp media cũ
        if self.movie:
            self.movie.stop()
            self.movie = None
        if self.media_player:
            self.media_player.stop()
            self.media_player = None
            self.video_sink = None
            self.audio_output = None
            
        if is_url:
            self.media_player = QMediaPlayer()
            self.audio_output = QAudioOutput()
            self.media_player.setAudioOutput(self.audio_output)
            
            self.video_sink = QVideoSink()
            self.media_player.setVideoOutput(self.video_sink)
            self.video_sink.videoFrameChanged.connect(self.on_video_frame)
            self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
            
            self.media_player.setSource(QUrl(path))
            self.media_player.play()
            
            self.label.hide()
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
            
            self.media_player.setSource(QUrl.fromLocalFile(path))
            self.media_player.play()
            
        else:
            self.pixmap = QPixmap(path)
            self.update() # Trigger paintEvent
            
        self.label.hide() # Hide text
        
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
    app.setApplicationName("Desktop Image Widget")
    
    widget = ImageWidget()
    
    # We use pythonw.exe to run without a console window usually, 
    # but running from terminal here is fine for testing.
    sys.exit(app.exec())
