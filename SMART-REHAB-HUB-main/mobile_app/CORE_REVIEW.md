# Core review và bàn giao prototype Flutter–Pi v2

## Đã sửa

- Bỏ listener `current_session`. Nhập ID phiên tường minh; chỉ đọc `sessions/<session_id>/latest`. `WorkoutSample` kiểm tra schema 2, ID phiên, mã bài, góc nullable, trạng thái, sequence và timestamp nguồn.
- Pi là nguồn quyết định bài. App chỉ quan sát, không đổi tên bài/reps cục bộ khi bấm chọn. Một phiên gắn một bài; thay bài phải mở phiên mới.
- `WorkoutSessionController` độc lập Firebase: từ chối dữ liệu sai phiên, dữ liệu trùng/đi lùi, giảm reps, đổi bài/bên giữa phiên. Có nguồn fixture offline, không ghi Firebase.
- Phân biệt waiting/selecting_side/tracking/lost/stale/error; stale sau 2 giây theo thời gian nhận hoặc tuổi gói epoch. Không hiện góc cũ như mẫu đo mới. Giữ reps đã hoàn thành khi mất khớp.
- Bỏ “Perfect Form”; nhận pose không có nghĩa tư thế đúng. Form luôn chưa đánh giá. `angle` là góc trong 2D, không phải điểm chất lượng.
- Logout gọi Firebase `signOut` khi Firebase được khởi tạo, hủy listener/timer và dừng TTS. Dispose cũng hủy đăng ký và dừng TTS. Offline demo không cần Firebase.
- QR/PIN/pairing, kết nối thiết bị, dữ liệu lịch sử/profile mẫu đều ghi rõ prototype/demo/unverified. Video Base64 bị bỏ khỏi đường dữ liệu v2; khung video ghi chưa kết nối.
- Thay avatar mạng giả bằng icon để fixture không phụ thuộc tải ảnh. Sửa tràn chữ ở viewport điện thoại 390×844, giữ bố cục/chức năng prototype.

## Chạy thử không cloud

```sh
flutter pub get --enforce-lockfile
flutter test --no-pub
flutter analyze --no-pub --no-fatal-infos
flutter run -d chrome --dart-define=REHAB_DEMO=true
```

Chọn **Use offline demo fixture**. Bản demo không khởi tạo Firebase, không tải font Google; nút cloud bị vô hiệu. Fixture là số liệu tổng hợp, không phải phép đo Pi và không kiểm chứng độ chính xác.

## Hợp đồng cần dùng khi nối Pi

Xem `../../mediapipe-benchmark/ALGORITHM_V2.md`. Bắt buộc schema 2, session ID khớp đường dẫn, `form_status=not_evaluated`. Reps là chu kỳ bắt đầu→đích→trở về; sample timestamp khác epoch thời gian gửi. App không chấp nhận `lateral_raise` như `shoulder_press`.

Chương trình Python legacy trong repo app chưa được chuyển thành publisher v2. Phiên này chỉ có pipeline benchmark dùng thuật toán mới + consumer/mock đúng hợp đồng. **Chưa kiểm thử đường truyền Pi→Firebase→điện thoại thực tế**, chưa triển khai kênh điều khiển hai chiều. Không chạy backend legacy rồi coi dữ liệu đó tương thích.

## Kiểm thử và giới hạn review

- **9/9 Flutter tests đạt**: bao phủ 5 mã bài, sai phiên, null, malformed data, stale/cache cũ, duplicate, đổi bài, binding lại, logout và dispose; có test màn hình nhỏ và khởi động app offline.
- Phân tích tĩnh không có error/warning; còn 31 mức info tồn tại từ prototype (`withOpacity`, `print`, style ở các màn hình cũ). Không đổi diện rộng ngoài scope.
- `flutter build web --no-pub --dart-define=REHAB_DEMO=true` đã build thành công (`build/web`). Không kết nối Firebase production trong kiểm thử; chưa chạy Android/iOS trên thiết bị thật. Web build offline chỉ xác nhận biên dịch, không phải E2E cloud.
- Chưa có Firebase Security Rules để review. Session ID **không phải cơ chế phân quyền**. Trước thử với dữ liệu người bệnh phải giới hạn owner/session/device trong Rules và kiểm thử bằng emulator; chưa kết luận bảo mật đạt.
- Epoch stale phụ thuộc đồng bộ đồng hồ; gói đi trước app >5 giây bị báo lỗi. Sau mất kết nối/gửi chậm, app không được suy ra người dùng đã tập đúng hoặc hoàn thành thêm rep.
- Lịch sử, hồ sơ mẫu, mục tiêu điều trị và ghi chú bác sĩ còn là demo có nhãn. Không dùng cho quyết định điều trị.

## File chính

`lib/workout_session.dart`, `lib/session_binding_screen.dart`, `lib/home_screen.dart`, `lib/main.dart`, `lib/pairing_screen.dart`, `test/*_test.dart`.

Bản trước sửa được giữ tại `/Volumes/Kingston/mediapipe-benchmark/review_v2/flutter_before_v2.tar.gz`. Không xóa source cũ hoặc benchmark cũ. Không thay package version hay Firebase Rules.
