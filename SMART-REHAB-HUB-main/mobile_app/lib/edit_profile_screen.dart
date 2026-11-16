// lib/edit_profile_screen.dart
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_database/firebase_database.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:image_picker/image_picker.dart';
import 'main.dart';

class EditProfileScreen extends StatefulWidget {
  final String currentName;
  final String currentCondition;
  final String currentHeight;
  final String currentWeight;
  final String? currentAvatarUrl; // Thêm biến chứa link ảnh hiện tại

  const EditProfileScreen({
    super.key,
    required this.currentName,
    required this.currentCondition,
    required this.currentHeight,
    required this.currentWeight,
    this.currentAvatarUrl,
  });

  @override
  State<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends State<EditProfileScreen> {
  late TextEditingController _nameController;
  late TextEditingController _heightController;
  late TextEditingController _weightController;
  late String selectedCondition;

  bool _isLoading = false;
  File? _imageFile; // Biến lưu file ảnh vừa chọn từ điện thoại

  final List<String> conditions = [
    'Post-Stroke Recovery',
    'Knee injury/ligament damage',
    'Spinal degeneration',
    'Shoulder stiffness',
  ];

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.currentName);

    // Xử lý chuỗi để loại bỏ chữ ' cm' và ' kg' khi đưa vào ô nhập liệu
    _heightController = TextEditingController(
        text: widget.currentHeight.replaceAll(RegExp(r'[^0-9.]'), ''));
    _weightController = TextEditingController(
        text: widget.currentWeight.replaceAll(RegExp(r'[^0-9.]'), ''));

    selectedCondition = conditions.contains(widget.currentCondition)
        ? widget.currentCondition
        : conditions[0];
  }

  @override
  void dispose() {
    _nameController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    super.dispose();
  }

  // HÀM MỞ THƯ VIỆN ẢNH ĐIỆN THOẠI
  Future<void> _pickImage() async {
    final picker = ImagePicker();
    final pickedFile =
        await picker.pickImage(source: ImageSource.gallery, imageQuality: 50);

    if (pickedFile != null) {
      setState(() {
        _imageFile = File(pickedFile.path);
      });
    }
  }

  // LƯU CẬP NHẬT LÊN FIREBASE (BAO GỒM CẢ ẢNH VÀ TEXT)
  Future<void> _saveChanges() async {
    final name = _nameController.text.trim();
    final heightStr = _heightController.text.trim();
    final weightStr = _weightController.text.trim();

    if (name.isEmpty || heightStr.isEmpty || weightStr.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            backgroundColor: Colors.red,
            content: Text('Please fill all fields!')),
      );
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final user = FirebaseAuth.instance.currentUser;
      if (user != null) {
        String? avatarUrl = widget.currentAvatarUrl;

        // 1. NẾU NGƯỜI DÙNG CÓ CHỌN ẢNH MỚI -> TẢI LÊN FIREBASE STORAGE
        if (_imageFile != null) {
          final storageRef = FirebaseStorage.instance
              .ref()
              .child('user_avatars/${user.uid}.jpg');
          await storageRef.putFile(_imageFile!);
          avatarUrl = await storageRef.getDownloadURL();

          // Cập nhật link ảnh vào Auth
          await user.updatePhotoURL(avatarUrl);
        }

        final height = double.tryParse(heightStr) ?? 165;
        final weight = double.tryParse(weightStr) ?? 60;
        final bmi =
            (weight / ((height / 100) * (height / 100))).toStringAsFixed(1);

        await user.updateDisplayName(name);

        // 2. LƯU TẤT CẢ VÀO REALTIME DATABASE
        await FirebaseDatabase.instance
            .ref('users/${user.uid}/profile')
            .update({
          'name': name,
          'height': height,
          'weight': weight,
          'bmi': bmi,
          'condition': selectedCondition,
          'avatarUrl': avatarUrl, // Lưu kèm link ảnh
          'updatedAt': DateTime.now().toIso8601String(),
        });
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              backgroundColor: AppColors.primary,
              content: Text('Profile updated successfully!')),
        );
        Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              backgroundColor: Colors.red, content: Text('Update failed: $e')),
        );
      }
    } finally {
      if (mounted)
        setState(() {
          _isLoading = false;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Edit Profile',
            style: TextStyle(
                color: AppColors.textDark,
                fontWeight: FontWeight.bold,
                fontSize: 18)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppColors.textDark),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // KHU VỰC THAY ĐỔI ẢNH ĐẠI DIỆN
              Center(
                child: Stack(
                  alignment: Alignment.bottomRight,
                  children: [
                    CircleAvatar(
                      radius: 55,
                      backgroundColor: Colors.grey.shade200,
                      backgroundImage: _imageFile != null
                          ? FileImage(_imageFile!)
                              as ImageProvider // Hiện ảnh vừa chọn
                          : (widget.currentAvatarUrl != null
                              ? NetworkImage(widget
                                  .currentAvatarUrl!) // Hiện ảnh cũ từ mạng
                              : const NetworkImage(
                                  'https://i.pravatar.cc/150?img=60')), // Trống thì hiện mặc định
                    ),
                    GestureDetector(
                      onTap: _pickImage,
                      child: Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: AppColors.primary,
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2),
                        ),
                        child: const Icon(Icons.camera_alt_rounded,
                            color: Colors.white, size: 20),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 30),

              _buildField('Full Name', 'Enter your name', Icons.person,
                  _nameController),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: _buildField('Height (cm)', 'e.g. 165', Icons.height,
                        _heightController,
                        isNumber: true),
                  ),
                  const SizedBox(width: 15),
                  Expanded(
                    child: _buildField('Weight (kg)', 'e.g. 60',
                        Icons.monitor_weight_outlined, _weightController,
                        isNumber: true),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              const Text('Recovery Status / Condition',
                  style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textDark)),
              const SizedBox(height: 8),
              Container(
                height: 55,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                decoration: BoxDecoration(
                    color: AppColors.cardBg,
                    borderRadius: BorderRadius.circular(16)),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<String>(
                    value: selectedCondition,
                    isExpanded: true,
                    icon: const Icon(Icons.keyboard_arrow_down,
                        color: AppColors.textGray),
                    items: conditions.map((String value) {
                      return DropdownMenuItem<String>(
                          value: value,
                          child: Text(value,
                              style: const TextStyle(
                                  color: AppColors.textDark, fontSize: 14)));
                    }).toList(),
                    onChanged: (val) {
                      if (val != null)
                        setState(() {
                          selectedCondition = val;
                        });
                    },
                  ),
                ),
              ),
              const SizedBox(height: 40),
              SizedBox(
                width: double.infinity,
                height: 55,
                child: ElevatedButton.icon(
                  onPressed: _isLoading ? null : _saveChanges,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16)),
                  ),
                  icon: _isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                              color: Colors.white, strokeWidth: 2))
                      : const Icon(Icons.save_rounded, color: Colors.white),
                  label: Text(
                    _isLoading ? 'SAVING...' : 'SAVE CHANGES',
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildField(String label, String hint, IconData icon,
      TextEditingController controller,
      {bool isNumber = false}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: AppColors.textDark)),
        const SizedBox(height: 8),
        TextField(
          controller: controller,
          keyboardType: isNumber ? TextInputType.number : TextInputType.text,
          decoration: InputDecoration(
            prefixIcon: Icon(icon, color: AppColors.textGray, size: 20),
            hintText: hint,
            hintStyle: const TextStyle(color: AppColors.textGray, fontSize: 14),
            filled: true,
            fillColor: AppColors.cardBg,
            border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide.none),
          ),
        ),
      ],
    );
  }
}
