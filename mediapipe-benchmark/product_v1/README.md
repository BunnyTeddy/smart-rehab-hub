# SMART REHAB — hub 1.1.2-rc2, Android 1.1.1-rc1

Đây là bản ứng viên để nghiệm thu. Chỉ đổi trạng thái thành final khi hoàn tất các bài kiểm trong `ACCEPTANCE.md`, bao gồm bài cuối tắt Mac.

## Cấu trúc

- App Android: `SMART-REHAB-HUB-main/mobile_app/lib/product`.
- Dashboard bác sĩ: `SMART-REHAB-HUB-main/web_dashboard/Live Workout/src/product`.
- Hub: `python -m product_v1.hub`, do systemd quản lý.
- Rules: `cloud/generate_rules.py`, namespace `rehab_v1`; triển khai bằng cách hợp nhất với Rules đang chạy.
- Thuật toán: giữ nguyên `pose_algorithm`, preset 2.0.0. Sáu bài mới dùng module riêng; giữ baseline squat/gập tay. Xem `exercises.json` và các báo cáo release cho phiên bản thực tế.

## Hợp đồng

`patients/{uid}/profile`, `patientHub/{uid}`, `hubs/{id}`, `hubState/{id}`, `commands/{id}/{command}`, `acks/{id}/{command}`, `sessions/{session}`, `patientSessions/{uid}/{session}`, `doctorDirectory/{doctor}`, `careLinks/{doctor}/{patient}`, `patientDoctors/{patient}/{doctor}`, `comments/{session}/{doctor}` đều nằm dưới `rehab_v1`.

Firebase custom claims: hub có `role=hub, hub_id=<id>` và UID khớp registry; bác sĩ có `role=doctor`. Tài khoản bệnh nhân không có claim đặc quyền. PatientDoctors chỉ là chỉ mục điều hướng; careLinks quyết định quyền. Mỗi hub và mỗi bệnh nhân chỉ ghép một lần. Thu hồi bác sĩ có hiệu lực ở Rules cho mọi lần đọc/ghi tiếp theo.

QR hub là JSON `{"v":1,"type":"hub","hub_id":"...","key":"<32 random bytes, base64>"}`. QR bác sĩ dùng `doctor_uid`, không có khóa. Mã hub là bí mật thiết lập, chỉ in trên thiết bị. BLE dùng AES-256-GCM, nonce ngẫu nhiên 12 byte, challenge ngẫu nhiên 16 byte, số thứ tự tăng từng chiều, hạn 120 giây. AAD: `smart-rehab:v1|hub_id|challenge|request/response|seq`. Payload trả về gồm `ok` và mã kết quả. App lưu khóa chủ hub trước khi gửi bằng Android encrypted storage. Hub lưu khóa ngoài source, file 0600. Mất điện ngay lúc nhận sở hữu có thể thử lại bằng khóa đã lưu; không đổi chủ hub.

Lệnh Firebase có thời hạn tối đa 30 giây. Hub ghi nhận ID và acknowledgement bằng SQLite trước khi mở engine. App chờ acknowledgement; điện thoại không giữ thời gian phiên. REST stream nghe lệnh, outbox gửi lại meta/events/points/summary bằng ID cố định. `latest` chỉ nằm trong RAM, tối đa 2 Hz, bỏ mẫu cũ trên 2 giây; mẫu biểu đồ tối đa 1 Hz. Summary và việc xóa trạng thái active được commit cùng transaction. Final history index được xếp sau summary. Khởi động lại kết thúc phiên dang dở, không tự mở camera.

TV dùng OpenCV Qt/Xwayland trên labwc, fullscreen, giữ tỷ lệ ảnh, ẩn con trỏ và thanh công cụ. TV chờ hiển thị trạng thái thật và hướng dẫn mở app, camera đóng. Từ RC2, camera/skeleton đúng frame được giữ trọn tỷ lệ ở chiều cao toàn màn hình. Tên bài và tiến độ nổi ở hai góc trên, nằm trong vùng an toàn cách mép tối thiểu 5%; không có hai thanh ngang làm nhỏ camera. Khi tập bình thường chỉ giữ tên bài và tiến độ; lời nhắc ngắn xuất hiện khi cần hoàn tất động tác hoặc xử lý lỗi. Màn hình chờ/tổng kết dùng một nội dung chính, không có các thẻ thống kê. Chuẩn bị gồm nạp model, năm frame làm nóng, phát xong lời hướng dẫn và READY liên tục trong đếm ngược 3–2–1; mất khớp hoặc rời tư thế đầu hủy đếm ngược. Sau đó mới bắt đầu thời gian/đếm của hiệp. Khi nghỉ vẫn giữ camera/pose và đồng hồ nghỉ. Kết thúc đóng camera, hiển thị tổng kết thực 15 giây rồi về chờ; sau 3 phút chờ nội dung mờ đi và dịch nhẹ vị trí mỗi phút. TV không hiển thị danh tính, QR hoặc nhận xét bác sĩ. Pillow và font DejaVu đi kèm hỗ trợ dấu tiếng Việt; cache đồ họa tránh vẽ chữ lại ở mỗi frame. Thiếu khớp hủy chu kỳ dở theo thuật toán v2. Mất cloud 10 giây, webcam/HDMI/âm thanh lỗi hoặc nhiệt đạt 80°C sẽ dừng. Camera không mở nếu âm thanh/HDMI chưa sẵn sàng.

## Cài kỹ thuật ban đầu

Gói cài đầy đủ kèm `device-assets` gồm Python 3.12 cho ARM64, model và wheelhouse đã kiểm tra trên Pi 4 Debian 13. Nếu dùng gói cập nhật nhỏ, trình cài lấy các thành phần này từ `/home/hoang1807/mediapipe-benchmark`. `install.sh` tạo release độc lập và venv riêng, không ghi đè thư mục benchmark. `install-system.sh <hub-user>` được chạy một lần bằng root để mở Bluetooth và cấp quyền NetworkManager cho tài khoản hub. Thiết bị cần cấu hình `.config/smart-rehab/product.json` (0600), chỉ có danh tính hub; không được chứa khóa quản trị Firebase.

`install.sh` đăng ký systemd user service và hook labwc. Tài khoản đồ họa Pi đã được cấu hình tự đăng nhập. Release mới chuyển symlink `current` sau khi pip check và unit tests đạt. `rollback.sh` từ chối nếu có phiên đang tập; giữ nguyên dữ liệu và ghép đôi. Với release đầu tiên, rollback tắt khởi động sản phẩm và quay về desktop/benchmark trước đó. Với release tiếp theo, nó chọn release trước. Các thay đổi quyền hệ thống được giữ để không tác động tới dữ liệu hoặc mạng đang dùng.

Khóa ký APK nằm ngoài source tại `~/.config/smart-rehab/android-release.jks`; properties 0600 được truyền bằng `REHAB_SIGNING_PROPERTIES`. Cần sao lưu riêng keystore/properties để cập nhật APK cùng chữ ký; không đặt chúng trong gói bàn giao công khai. Application ID `com.smartrehabhub.patient`, minSdk 26.

Tạo bác sĩ: quản trị viên chạy `python -m product_v1.cloud.provision_doctor --email <email> --name <name>` trên máy triển khai đã đăng nhập gcloud. Công cụ không thay mật khẩu tài khoản đã tồn tại, không gửi email và không đưa mật khẩu ra stdout. File tài khoản ban đầu nằm trong thư mục private bên ngoài source.

## Giọng nói

Theo lựa chọn của người dùng ngày 04/10/2026, RC3 dùng **Piper tiếng Việt, vi_VN-vais1000-medium**. Đây là thay đổi nhà cung cấp so với kế hoạch FPT lannhi ban đầu; không xác nhận đây là giọng nữ miền Nam. Không cần tài khoản, API key hoặc thanh toán. Chất lượng nghe trên loa hub vẫn phải được người nghe xác nhận trước nghiệm thu final.

Trên máy tạo âm thanh, dùng Python 3.13, `piper-tts==1.8.0` và ffmpeg; tải model bằng `python -m piper.download_voices vi_VN-vais1000-medium --download-dir <model-dir>`. Tạo bộ bằng `python -m product_v1.make_piper_pack --model <model-dir>/vi_VN-vais1000-medium.onnx --output <audio-dir>`; có tùy chọn `--sample-only`. Bộ có 12 câu và 200 số đếm, PCM 16-bit/mono/22.05 kHz. Manifest lưu nội dung, độ dài, SHA-256, phiên bản Piper và checksum model. `ATTRIBUTION.md` đi cùng bộ âm thanh.

Khi tập, Pi chỉ chạy aplay phát WAV cục bộ. Engine/model Piper không cài vào runtime của Pi và không tranh tài nguyên suy luận với MediaPipe. Bộ âm thanh đi trong từng release, được kiểm tra đủ 212 tệp, checksum và WAV hợp lệ trước khi kích hoạt. `audio_ready=true` chỉ xác nhận bộ tệp hợp lệ, không thay cho nghiệm thu người nghe. Nút thắt API FPT đã được bỏ; hub vẫn cần Firebase để vận hành phiên. Công cụ FPT cũ chỉ giữ làm lịch sử và không dùng để tạo bản mới.

## Kiểm tra

Python: `python -m unittest discover -s product_v1/tests`. Firebase Rules: `node --test product_v1/cloud/rules.test.mjs` với RTDB emulator cổng 19000. Chạy Rules tests trước UI emulator vì bộ này xóa database emulator để cô lập từng test. `python -m product_v1.tests.e2e_emulator` kiểm tra Auth, Rules, REST stream, outbox, ack, lịch sử và nhận xét; engine trong bài này là mô phỏng, không thay nghiệm thu người thật. Auth emulator dùng cổng 19099, namespace `demo-smart-rehab-product`.

Flutter: `flutter analyze lib/product lib/main.dart`, `flutter test`. Web: `node --test src/product/data.test.mjs src/integration/session.test.mjs`, `npm run build -- --outDir build-product`. UI fixtures chỉ ở emulator; không có số liệu mẫu tự chèn vào production.

Giới hạn Spark cần được quản trị theo dõi trong Firebase Console. Giao diện hiện thống kê 100 buổi gần nhất. Không tự xóa lịch sử khi gần hạn mức và không tự chuyển sang gói trả phí.

## Nguồn đặc tả triển khai

- Piper: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md
- Giọng và nguồn dữ liệu VAIS-1000: https://huggingface.co/rhasspy/piper-voices/blob/main/vi/vi_VN/vais1000/medium/MODEL_CARD
- Firebase đăng ký chứng thư Android: https://firebase.google.com/docs/reference/firebase-management/rest/v1beta1/projects.androidApps.sha/create

## Đóng gói và phân phối

Chạy `python -m product_v1.package_release --assets <pi-device-assets.tar.gz> --audio <audio-dir> --output <release-dir>` để tạo bộ cài đầy đủ và gói cập nhật nhỏ, kèm manifest SHA-256 mã nguồn và âm thanh. Gói không có khóa quản trị, tài khoản hub, QR ghép đôi hoặc khóa ký APK. Bản đầy đủ cài dependency offline; các thư viện hệ thống/desktop vẫn cần nền Debian 13 labwc trên Pi đã chuẩn bị. Android giữ bản RC2/build 2 vì giao thức điều khiển không thay đổi. Rollback hub về RC2 sẽ trở lại trạng thái cũ chưa có bộ giọng; dữ liệu và ghép đôi được giữ nguyên.

APK đã ký được bàn giao riêng để cài lần đầu. Firebase Spark từ chối tệp APK trên Hosting; không đổi đuôi để lách giới hạn và không nâng gói trả phí. Trang `/tai-app/` chỉ có thông tin bản cài/checksum và `/huong-dan/` có hướng dẫn bằng giao diện. Nguồn giới hạn: https://firebase.google.com/support/faq#hosting-exe-restrictions
