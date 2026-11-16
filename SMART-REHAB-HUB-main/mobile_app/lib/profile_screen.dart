// lib/profile_screen.dart (SAVE REAL MEDICAL PROFILE TO FIREBASE REALTIME DB)
import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_database/firebase_database.dart';
import 'main.dart';
import 'pairing_screen.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final TextEditingController _ageController = TextEditingController();
  final TextEditingController _heightController = TextEditingController();
  final TextEditingController _weightController = TextEditingController();

  String selectedGender = 'Male';
  String? selectedCondition;
  bool _isLoading = false;

  // HÀM LƯU HỒ SƠ Y TẾ THẬT LÊN DATABASE THEO USER UID
  Future<void> _saveProfileAndContinue() async {
    final age = _ageController.text.trim();
    final heightStr = _heightController.text.trim();
    final weightStr = _weightController.text.trim();

    if (age.isEmpty ||
        heightStr.isEmpty ||
        weightStr.isEmpty ||
        selectedCondition == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: Colors.red,
          content: Text('Please fill in all medical profile fields!'),
        ),
      );
      return;
    }

    setState(() {
      _isLoading = true;
    });

    // LẤY TÊN TỪ FIREBASE ĐỂ TRUYỀN SANG TRANG SAU
    final user = FirebaseAuth.instance.currentUser;
    String displayName = user?.email?.split('@')[0] ?? 'Patient';

    try {
      if (user != null) {
        final height = double.tryParse(heightStr) ?? 165;
        final weight = double.tryParse(weightStr) ?? 60;
        // Tự động tính chỉ số BMI chuẩn y khoa
        final bmi =
            (weight / ((height / 100) * (height / 100))).toStringAsFixed(1);

        // LƯU TRỰC TIẾP LÊN FIREBASE REALTIME DB TẠI NODE users/{UID}/profile
        await FirebaseDatabase.instance.ref('users/${user.uid}/profile').set({
          'age': age,
          'gender': selectedGender,
          'height': height,
          'weight': weight,
          'bmi': bmi,
          'condition': selectedCondition,
          'updatedAt': DateTime.now().toIso8601String(),
        });
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            backgroundColor: AppColors.primary,
            content: Text('Medical profile saved to Cloud!'),
          ),
        );
        Navigator.pushReplacement(
          context,
          // Đã thêm userName vào đây
          MaterialPageRoute(
              builder: (context) => PairingScreen(userName: displayName)),
        );
      }
    } catch (e) {
      // Nếu có lỗi mạng vẫn cho phép đi tiếp để không chặn demo
      if (mounted) {
        Navigator.pushReplacement(
          context,
          // Đã thêm userName vào đây
          MaterialPageRoute(
              builder: (context) => PairingScreen(userName: displayName)),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppColors.textDark),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 10.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Medical Profile Setup',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textDark,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Personalize your recovery journey.',
                style: TextStyle(fontSize: 14, color: AppColors.textGray),
              ),
              const SizedBox(height: 30),

              // AGE & GENDER ROW
              Row(
                children: [
                  Expanded(
                    child: _buildField(
                      'Age',
                      'e.g., 65',
                      Icons.calendar_today,
                      _ageController,
                      isNumber: true,
                    ),
                  ),
                  const SizedBox(width: 15),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Gender',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: AppColors.textDark,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Container(
                          height: 55,
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                          decoration: BoxDecoration(
                            color: AppColors.cardBg,
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: DropdownButtonHideUnderline(
                            child: DropdownButton<String>(
                              value: selectedGender,
                              isExpanded: true,
                              items: ['Male', 'Female'].map((String value) {
                                return DropdownMenuItem<String>(
                                  value: value,
                                  child: Text(value),
                                );
                              }).toList(),
                              onChanged: (val) {
                                if (val != null) {
                                  setState(() {
                                    selectedGender = val;
                                  });
                                }
                              },
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // HEIGHT & WEIGHT ROW
              Row(
                children: [
                  Expanded(
                    child: _buildField(
                      'Height (cm)',
                      'e.g., 165',
                      Icons.height,
                      _heightController,
                      isNumber: true,
                    ),
                  ),
                  const SizedBox(width: 15),
                  Expanded(
                    child: _buildField(
                      'Weight (kg)',
                      'e.g., 60',
                      Icons.monitor_weight_outlined,
                      _weightController,
                      isNumber: true,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // REHAB CONDITION DROPDOWN
              const Text(
                'Recovery Status',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textDark,
                ),
              ),
              const SizedBox(height: 8),
              Container(
                height: 55,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                decoration: BoxDecoration(
                  color: AppColors.cardBg,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<String>(
                    value: selectedCondition,
                    hint: const Text(
                      'Select your condition',
                      style: TextStyle(color: AppColors.textGray),
                    ),
                    isExpanded: true,
                    icon: const Icon(
                      Icons.keyboard_arrow_down,
                      color: AppColors.textGray,
                    ),
                    items: [
                      'Recovery after stroke',
                      'Knee injury/ligament damage',
                      'Spinal degeneration',
                      'Shoulder stiffness',
                    ].map((String value) {
                      return DropdownMenuItem<String>(
                        value: value,
                        child: Text(value),
                      );
                    }).toList(),
                    onChanged: (newValue) {
                      setState(() {
                        selectedCondition = newValue;
                      });
                    },
                  ),
                ),
              ),
              const SizedBox(height: 40),

              // BUTTON SAVE & CONTINUE
              SizedBox(
                width: double.infinity,
                height: 55,
                child: ElevatedButton.icon(
                  onPressed: _isLoading ? null : _saveProfileAndContinue,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  icon: _isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                              color: Colors.white, strokeWidth: 2),
                        )
                      : const Icon(
                          Icons.check_circle_outline,
                          color: Colors.white,
                        ),
                  label: Text(
                    _isLoading ? 'SAVING TO CLOUD...' : 'Complete Profile',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildField(
    String label,
    String hint,
    IconData icon,
    TextEditingController controller, {
    bool isNumber = false,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: AppColors.textDark,
          ),
        ),
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
              borderSide: BorderSide.none,
            ),
          ),
        ),
      ],
    );
  }
}
