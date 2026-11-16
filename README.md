# SMART REHAB Hub

SMART REHAB hỗ trợ luyện tập tại nhà trên Raspberry Pi 4 với webcam USB và TV. Hub dùng OpenCV và MediaPipe Pose Landmarker Lite để tính góc khớp và đếm chu kỳ. Bệnh nhân điều khiển phiên trên Android. Bác sĩ xem kết quả của bệnh nhân đã cấp quyền qua dashboard. Firebase đồng bộ góc, tiến độ và lịch sử, còn hình ảnh camera được xử lý tại Hub.

Mốc mã nguồn trong repo là **Hub 1.2.1-rc3** và **Android 1.2.1-rc3, build 9**. Thư viện hiện có squat, gập tay, nâng tay ra trước và dạng tay sang bên. Siêu dữ liệu bài cũ được giữ để đọc lịch sử. Cấu hình nhận diện bốn bài nằm trong `mediapipe-benchmark/product_v1/detection_presets.json`.

| Thành phần | Thư mục |
|---|---|
| Hub, BLE, phiên tập, SQLite và hiển thị TV | `mediapipe-benchmark/product_v1/` |
| Thuật toán góc 2D, EMA và FSM | `mediapipe-benchmark/pose_algorithm/` |
| Transport Firebase và thư viện dùng chung | `mediapipe-benchmark/integration_v1/` |
| Firebase Rules và công cụ triển khai | `mediapipe-benchmark/product_v1/cloud/` |
| Ứng dụng bệnh nhân | `SMART-REHAB-HUB-main/mobile_app/` |
| Dashboard bác sĩ | `SMART-REHAB-HUB-main/web_dashboard/Live Workout/` |

## Kiểm tra cục bộ

Hub dùng Python 3.12. Cài các gói phục vụ kiểm thử trong môi trường ảo.

```sh
cd mediapipe-benchmark
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install numpy==1.26.4 opencv-python-headless==4.10.0.84 pillow cryptography dbus-fast qrcode
python -m unittest discover -s product_v1/tests -q
python -m unittest test_algorithm_v2 -q
python -m product_v1.cloud.generate_catalog --check
```

Lệnh cuối cần Dart từ Flutter SDK trong `PATH`. Khi thay đổi `product_v1/exercises.json`, chạy `python -m product_v1.cloud.generate_catalog` để cập nhật danh mục của cả hai client.

Ứng dụng Flutter cần Flutter SDK, Android SDK và JDK 17 để build Android. Từ gốc repo, chạy:

```sh
cd SMART-REHAB-HUB-main/mobile_app
flutter pub get
flutter test
flutter run
```

Để ký một APK release, đặt `REHAB_SIGNING_PROPERTIES` trỏ đến tệp riêng chứa `storeFile`, `storePassword`, `keyAlias` và `keyPassword`, rồi chạy `flutter build apk --release`.

Dashboard cần Node.js và npm. Từ gốc repo, chạy:

```sh
cd 'SMART-REHAB-HUB-main/web_dashboard/Live Workout'
npm ci
node --test src/product/data.test.mjs src/integration/session.test.mjs
npm run dev
```

`npm run build` tạo bản web tĩnh. Hai client dùng cấu hình Firebase đã đăng ký của dự án. Chế độ dashboard chạy với Firebase Emulator dùng `VITE_PRODUCT_EMULATOR=true`.

Firebase Rules trong `product_v1/cloud/database.rules.json` là bản đang có trong bộ nguồn, còn hỗ trợ các mã bài của Hub cũ. Trình sinh Rules lấy danh mục bốn bài hiện hành, nên kết quả sinh lại sẽ thu hẹp danh mục hợp lệ. Để kiểm tra bản Rules đi kèm, dùng JDK 21 và chạy từ `mediapipe-benchmark/`:

```sh
npm ci --prefix integration_v1/firebase
integration_v1/firebase/node_modules/.bin/firebase emulators:exec \
  --project demo-smart-rehab-product --config product_v1/cloud/firebase.json \
  --only database 'node --test product_v1/cloud/rules.test.mjs'
```

## Cài trên Pi

Hub thực tế chạy trên Raspberry Pi 4 ARM64, Debian 13 và labwc. Bộ cài đầy đủ cần gói tài nguyên ARM64 gồm Python, wheelhouse và model Lite. Dùng bộ WAV tiếng Việt đã tạo bằng Piper hoặc tạo lại bằng `product_v1.make_piper_pack`. Wheel các phụ thuộc bổ sung của Hub và font TV được giữ trong repo để hỗ trợ cài offline.

Từ `mediapipe-benchmark/`, tạo bộ cài với đường dẫn tài nguyên của bạn:

```sh
python -m product_v1.package_release \
  --assets /path/to/pi-device-assets.tar.gz \
  --audio /path/to/piper-wav-pack \
  --output ./releases/local
```

Sau khi giải nén bộ cài đầy đủ trên Pi, dùng `product_v1/install.sh` và các bước thiết lập trong [hướng dẫn Hub](mediapipe-benchmark/product_v1/README.md). Hướng dẫn Hub có một số ghi chú phiên bản lịch sử. Cấu hình HDMI 720p dùng trong đợt triển khai này nằm trong `mediapipe-benchmark/deployment/display/`. Tệp danh tính Hub `~/.config/smart-rehab/product.json`, khóa ký Android và thông tin quản trị Firebase được chuẩn bị riêng. Gói tài nguyên Pi đầy đủ, bản cài APK và dữ liệu phiên tập được lưu ngoài Git.
