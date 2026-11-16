# Phiếu nghiệm thu hub 1.0.0-rc3 / Android 1.0.0-rc2

Không đánh dấu final chỉ vì build, tiến trình hay unit test thành công. Bằng chứng tự động nằm trong thư mục release; người duyệt bổ sung thời gian, thiết bị và kết quả cho từng hàng dưới đây.

| Nhóm | Bài kiểm | Bằng chứng cần | Trạng thái |
|---|---|---|---|
| Phần mềm | Python contract/lifecycle/audio, Rules, Flutter, web | Log test và mã phiên bản | Đạt: 23 Python (RC3); 14 Rules, 21 Flutter, 9 web và analyze sạch ở RC2, không thay đổi các thành phần đó |
| Cloud | Lệnh REST streaming → ack → latest → summary → lịch sử → nhận xét | Kiểm thử emulator với Rules thực | Đạt trên emulator: luồng transport thực, engine mô phỏng |
| Android | APK chữ ký riêng, ID com.smartrehabhub.patient, Android 8+ | apksigner/aapt + checksum | Đạt: RC2 build 2, ký RSA-3072/v2, minSdk 26; SHA-256 trong apk-release.json |
| Quyền | Hai bệnh nhân không đọc chéo; bác sĩ cấp/chưa cấp/thu hồi; hub sai chủ; không tự nâng quyền | Rules tests + kiểm tra giao diện | Tự động đã đạt; nghiệm thu người dùng còn chờ |
| Khôi phục phiên bản | Quay RC2 → RC1 → RC2, dữ liệu local còn nguyên | pi-rollback-test.log, SQLite integrity_check | Đạt; cuối bài hub chạy RC2 |
| Ghép nối | QR sai, từ chối Bluetooth, Wi-Fi sai, đổi mạng, ngắt lúc ghép, thử chiếm hub | Android thật + hub BLE/NetworkManager | Chưa nghiệm thu |
| Khởi động | Dịch vụ tự lên sau reboot, BLE quảng bá, camera vẫn đóng | Pi thật + heartbeat Firebase | Đạt trên Pi: reboot tự chạy, NRestarts=0, BLE quảng bá, display_ready=true, camera đóng |
| Phiên | Bắt đầu hai lần, lệnh hết hạn, khóa/mở app, dừng, reboot, rút webcam, mất Internet | Android + Pi + TV | Chưa nghiệm thu toàn tuyến |
| Đếm squat | 3 lượt, mỗi lượt 5 chu kỳ hoàn chỉnh | Người duyệt đối chiếu 5/5 từng lượt | Chưa nghiệm thu |
| Đếm gập tay | 3 lượt, mỗi lượt 5 chu kỳ hoàn chỉnh | Người duyệt đối chiếu 5/5 từng lượt | Chưa nghiệm thu |
| Không đếm sai | Mất khớp, che khớp, động tác dở | Số rep không tăng | Chưa nghiệm thu người thật |
| Âm thanh | Piper tiếng Việt theo lựa chọn mới, câu ngắn, đếm 1–200, không chồng tiếng | Người nghe trên loa hub xác nhận | Đã tạo đủ 212 WAV, kiểm tra checksum/PCM/độ dài/tín hiệu; chưa nghiệm thu người nghe |
| Hiệu năng | 10 phút đồng thời TV/audio/cloud | Nhiệt <80°C, throttle=0, không lỗi lưu trữ, FPS giảm ≤10% so baseline cùng điều kiện | Chưa nghiệm thu |
| Bài cuối | Tắt Mac, reboot hub, dùng Android bắt đầu/dừng; dashboard từ thiết bị khác qua Internet | Người duyệt xác nhận | Chưa nghiệm thu |

Các mẫu và phiên emulator không được tính vào các lượt người thật. Không dùng điểm “hồi phục” hoặc “đúng tư thế” để thay số liệu chưa đo. Các bản ghi benchmark cũ được giữ nguyên.

Ngày 04/10/2026 người dùng chọn Piper thay FPT và hoãn thử Android/TV/người tập. Giọng VAIS-1000 chưa được xác nhận là nữ miền Nam. RC3 đóng gói âm thanh cục bộ; trạng thái file hợp lệ hoặc tiến trình aplay thành công không tự chuyển hàng nghiệm thu âm thanh sang Đạt.

## Mẫu ghi nhận một lượt thật

- Ngày giờ / người duyệt:
- Phiên bản APK / hub / dashboard:
- Bài tập / session ID / thời lượng:
- Số chu kỳ người duyệt đếm / số rep hệ thống:
- Tình huống mất khớp / chuyển động dở / kết quả:
- Kết quả app và dashboard có trùng nhau:
- Giọng trên loa có rõ và dễ nghe:
- Nhiệt cao nhất / throttled / FPS / baseline / lưu trữ:
- Đạt hoặc lỗi cần sửa:
