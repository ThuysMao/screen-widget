# Desktop Image Widget (screen-widget)

Một tiện ích hiển thị đa phương tiện (ảnh/video) trên màn hình Desktop (tương tự như widget trên điện thoại) được viết bằng Python (PyQt6). Ứng dụng này giúp bạn có thể treo bất kỳ bức ảnh hay video nào trên màn hình máy tính với thiết kế không viền, đẹp mắt và luôn hiển thị trên cùng (Always on top).

## ✨ Tính năng nổi bật

- **Thiết kế hiện đại:** Giao diện không viền (frameless) với hiệu ứng nền mờ (Glassmorphism) cực kỳ bắt mắt.
- **Luôn nổi trên cùng (Always on top):** Giúp bức ảnh/video yêu thích của bạn luôn hiển thị mà không bị các cửa sổ khác che lấp.
- **Hỗ trợ đa phương tiện:** Không chỉ ảnh tĩnh, widget còn hỗ trợ phát ảnh động (GIF), các định dạng video cục bộ (mp4, mkv, avi...) và phát trực tiếp video từ link **YouTube/Facebook**.
- **Chất lượng YouTube HD siêu nét:** Nhờ tích hợp lõi trình duyệt Chromium (`PyQt6-WebEngine`), widget có thể nhúng trực tiếp Trình phát gốc của YouTube, tự động đẩy độ phân giải lên cao nhất (1080p, 2K, 4K) thay vì bị giới hạn ở 720p/360p như thông thường.
- **Hiệu ứng viền & Bo góc:** Media tự động được bo góc mượt mà (radius 15px) và bao quanh bởi một đường viền mờ 5px tạo cảm giác như khung ảnh thật. Khi phóng to, hình ảnh luôn giữ đúng tỷ lệ gốc không bị bóp méo.
- **Thao tác nhanh chóng:** Hỗ trợ dán link trực tiếp ngay trên giao diện chính, nhấp đúp (Double-click) hoặc kéo thả (Drag & Drop) file trực tiếp vào widget để hiển thị ngay lập tức.
- **Tùy chỉnh kích thước:** Bạn có thể kéo các viền (kể cả viền tàng hình 10px bọc quanh YouTube) hoặc các góc của widget để phóng to/thu nhỏ khung hình một cách linh hoạt, hoặc dùng Menu chuột phải để chọn các kích thước có sẵn.
- **Điều khiển YouTube-style tinh tế:** 
  - Giao diện phím bấm ẩn trong suốt, hiện lên khi rê chuột vào giống YouTube.
  - Hỗ trợ các nút **Tạm dừng/Tiếp tục (⏸/▶)**, **Tua lui 10s (⏪)**, **Tua tới 10s (⏩)**.
  - **Nút Âm lượng (🔊)** thông minh: click vào biểu tượng loa để tắt/mở tiếng nhanh (Mute), hoặc rê chuột vào loa để bung mở thanh trượt chỉnh âm lượng.

## 🚀 Hướng dẫn sử dụng

### 1. Khởi chạy ứng dụng
- **Cách nhanh nhất:** Nhấn đúp vào file `widget.exe` để chạy ứng dụng trực tiếp mà không cần cài đặt thêm môi trường.

### 2. Tải Media (Ảnh/Video/Link) lên widget
- **Cách 1 (Nhanh nhất cho Link):** Dán trực tiếp link video YouTube hoặc Facebook vào ô nhập link ngay trên giao diện chính của widget và nhấn **Enter**.
- **Cách 2:** Nhấp đúp chuột trái vào khoảng trống của widget, một cửa sổ chọn file sẽ hiện ra để bạn tìm ảnh hoặc video từ máy tính. *(Lưu ý: Nhấp đúp chỉ hoạt động khi đang ở trạng thái ảnh/GIF hoặc chưa tải media, không hoạt động khi đang phát video để tránh thao tác nhầm)*
- **Cách 3:** Kéo trực tiếp một file media (`.png`, `.jpg`, `.gif`, `.mp4`, `.avi`,...) từ máy tính và thả vào bên trong widget.

### 3. Tương tác với widget
- **Di chuyển:** Nhấn giữ chuột trái vào video/ảnh (hoặc nhấn giữ viền mờ bên ngoài video) và kéo để di chuyển khung hình đến vị trí mong muốn.
- **Thay đổi kích thước tự do:** Đưa chuột ra các viền hoặc các góc của widget (con trỏ chuột sẽ đổi biểu tượng), sau đó nhấn giữ và kéo để thay đổi kích thước tùy ý.
- **Cụm phím điều khiển Video (Góc dưới trái):**
  - Nhấn ⏸ để Tạm dừng, ▶ để Tiếp tục.
  - Nhấn ⏪ hoặc ⏩ để tua lui/tới 10 giây.
  - Rê chuột vào biểu tượng 🔊 để mở thanh kéo âm lượng, click vào biểu tượng 🔊 để Mute tiếng nhanh.
- **Mở Menu tùy chọn:** Nhấn chuột phải vào widget để mở Menu, tại đây bạn có thể:
  - Chọn một file Media mới.
  - Nhập link YouTube/Facebook thủ công.
  - Chuyển đổi nhanh giữa các kích thước chuẩn (Vuông 300x300, Dọc 300x450, Ngang 450x300).
  - Thoát hoàn toàn khỏi ứng dụng.

## 🛠 Dành cho Nhà phát triển (Developer)

Nếu bạn muốn chạy ứng dụng từ mã nguồn (source code) hoặc muốn chỉnh sửa lại cho phù hợp:

1. Đảm bảo máy tính đã cài đặt Python 3.
2. Cài đặt thư viện yêu cầu:
   ```bash
   pip install PyQt6 PyQt6-WebEngine yt-dlp
   ```
3. Chạy file mã nguồn:
   ```bash
   python dist/widget.py
   ```
*(Bạn cũng có thể dùng `run_widget.vbs` để chạy ngầm không hiện cửa sổ dòng lệnh Console)*

---
*Được phát triển với PyQt6 & Python.*