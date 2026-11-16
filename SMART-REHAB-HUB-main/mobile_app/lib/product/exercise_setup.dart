import 'dart:async';
import 'package:flutter/material.dart';
import 'api.dart';
import 'contract.dart';
import 'app.dart' show Panel, InfoBox, notice, ink, green;

class ExerciseSetupPage extends StatefulWidget {
  final RehabApi api;
  final String hubId, exerciseId;
  final Map<String, dynamic> initialState;
  const ExerciseSetupPage(
      {super.key,
      required this.api,
      required this.hubId,
      required this.exerciseId,
      required this.initialState});
  @override
  State<ExerciseSetupPage> createState() => _ExerciseSetupPageState();
}

class _ExerciseSetupPageState extends State<ExerciseSetupPage> {
  String side = 'left', mode = 'time';
  int minutes = 3, legacyMinutes = 3, reps = 5, sets = 1, rest = 30;
  bool busy = false, connected = false;
  late Map<String, dynamic> hub;
  late StreamSubscription stateSubscription, connectionSubscription;
  late Timer timer;
  @override
  void initState() {
    super.initState();
    hub = widget.initialState;
    stateSubscription =
        widget.api.watch('hubState/${widget.hubId}').listen((value) {
      if (mounted) setState(() => hub = value);
    }, onError: (_) {
      if (mounted) setState(() => hub = {});
    });
    connectionSubscription = widget.api.connection.listen((value) {
      if (mounted) setState(() => connected = value);
    });
    timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    stateSubscription.cancel();
    connectionSubscription.cancel();
    timer.cancel();
    super.dispose();
  }

  Future<void> start() async {
    setState(() => busy = true);
    try {
      final modern = supportsProtocol2(hub);
      if (side == 'both' && !supportsBoth(hub, widget.exerciseId)) {
        throw const FormatException(
            'Hub cần được cập nhật để tập cả hai bên cùng lúc.');
      }
      await widget.api.command(widget.hubId, 'start',
          exercise: widget.exerciseId,
          duration: modern ? null : legacyMinutes * 60,
          requestedSide: modern
              ? (exerciseDetails(widget.exerciseId)['side_mode'] == 'required'
                  ? side
                  : 'auto')
              : null,
          goal: modern
              ? (mode == 'time'
                  ? {'mode': 'time', 'duration_s': minutes * 60}
                  : {
                      'mode': 'sets',
                      'reps_per_set': reps,
                      'sets': sets,
                      'rest_s': rest
                    })
              : null);
      if (mounted) Navigator.pop(context);
    } catch (error) {
      if (mounted) notice(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget choices(String title, List<int> values, int selected,
          void Function(int) choose, String Function(int) label) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SizedBox(height: 16),
        Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        Wrap(
            spacing: 8,
            runSpacing: 6,
            children: values
                .map((v) => ChoiceChip(
                    label: Text(label(v)),
                    selected: v == selected,
                    onSelected: busy ? null : (_) => setState(() => choose(v))))
                .toList()),
      ]);

  Widget durationSlider(String title, int value, int min, int max, int step,
          void Function(int) choose, String unit, String key) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SizedBox(height: 16),
        Text('$title: $value $unit',
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 18)),
        Slider(
          key: ValueKey(key),
          value: value.toDouble(),
          min: min.toDouble(),
          max: max.toDouble(),
          divisions: (max - min) ~/ step,
          label: '$value $unit',
          semanticFormatterCallback: (v) => '${v.round()} $unit',
          onChanged: busy ? null : (v) => setState(() => choose(v.round())),
        ),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Expanded(child: Text('$min $unit')),
          Expanded(child: Text('$max $unit', textAlign: TextAlign.end)),
        ]),
      ]);
  @override
  Widget build(BuildContext context) {
    final e = exerciseDetails(widget.exerciseId),
        modern = supportsProtocol2(hub);
    final online = connected &&
        DateTime.now().millisecondsSinceEpoch - number(hub['updated_at']) <
            8000;
    final active = hub['session_id'] is String &&
        ['preparing', 'aligning', 'running', 'stopping'].contains(hub['state']);
    return Scaffold(
        appBar: AppBar(title: Text(e['name'] ?? 'Chuẩn bị tập')),
        body: ListView(padding: const EdgeInsets.all(20), children: [
          ExerciseInstructions(
              exerciseId: widget.exerciseId, both: side == 'both'),
          Panel(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                if (modern && e['side_mode'] == 'required') ...[
                  const Text('Bên tập trong buổi này',
                      style: TextStyle(fontWeight: FontWeight.w700)),
                  const Text(
                      'Trái/phải là bên cơ thể bạn, dù hình trên TV phản chiếu.'),
                  Wrap(
                      spacing: 8,
                      children: [
                        'left',
                        'right',
                        if (supportsBoth(hub, widget.exerciseId)) 'both'
                      ]
                          .map((v) => ChoiceChip(
                              label: Text(sideText(v)),
                              selected: side == v,
                              onSelected: busy
                                  ? null
                                  : (_) => setState(() => side = v)))
                          .toList()),
                  if (side == 'both')
                    const InfoBox(
                        'Hai bên tập đồng thời. Cả hai phải cùng đạt vị trí cuối và cùng trở về mới tính một lần. Mục tiêu là số lần chung, không cộng riêng trái và phải.'),
                  if (e['bilateral'] == true &&
                      !supportsBoth(hub, widget.exerciseId))
                    const Text('Cập nhật hub để mở lựa chọn Cả hai cùng lúc.'),
                  if (widget.exerciseId == 'standing_hip_abduction')
                    const Text('Bài này cần một chân trụ nên tập từng chân.'),
                  const SizedBox(height: 20),
                ],
                if (modern) ...[
                  const Text('Bạn muốn tập theo cách nào?',
                      style: TextStyle(fontWeight: FontWeight.w700)),
                  Wrap(spacing: 8, children: [
                    ChoiceChip(
                        label: const Text('Theo thời gian'),
                        selected: mode == 'time',
                        onSelected:
                            busy ? null : (_) => setState(() => mode = 'time')),
                    ChoiceChip(
                        label: const Text('Theo lần và hiệp'),
                        selected: mode == 'sets',
                        onSelected:
                            busy ? null : (_) => setState(() => mode = 'sets'))
                  ]),
                ] else
                  const InfoBox(
                      'Hub hiện chỉ hỗ trợ thời lượng 3, 5 hoặc 10 phút. Hub tự chọn bên nhìn rõ để đo.'),
                if (modern && mode == 'time')
                  durationSlider('Thời lượng', minutes, 1, 10, 1,
                      (v) => minutes = v, 'phút', 'duration-slider'),
                if (!modern)
                  choices('Thời lượng', [3, 5, 10], legacyMinutes,
                      (v) => legacyMinutes = v, (v) => '$v phút'),
                if (modern && mode == 'sets') ...[
                  choices('Số lần mỗi hiệp', [5, 10, 15], reps, (v) => reps = v,
                      (v) => '$v lần'),
                  choices('Số hiệp', [1, 2, 3], sets, (v) => sets = v,
                      (v) => '$v hiệp'),
                  if (sets > 1)
                    durationSlider('Nghỉ giữa hiệp', rest, 15, 120, 15,
                        (v) => rest = v, 'giây', 'rest-slider'),
                  const InfoBox(
                      'Hub tự đếm nghỉ. Hết nghỉ, về tư thế đầu và chờ lời nhắc để bắt đầu hiệp tiếp theo.'),
                ],
                const SizedBox(height: 20),
                if (!online)
                  const InfoBox(
                      'Đang chờ kết nối với hub. Bạn kiểm tra Internet nhé.'),
                if (active) ...[
                  const InfoBox(
                      'Hub đang có một buổi tập. Trở về màn hình Tập luyện để xem và dừng.'),
                  TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Về buổi đang tập')),
                ],
                SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                        onPressed: busy ||
                                !online ||
                                active ||
                                (side == 'both' &&
                                    !supportsBoth(hub, widget.exerciseId)) ||
                                hub['ready'] != true ||
                                !supportsExercise(hub, widget.exerciseId)
                            ? null
                            : start,
                        icon: const Icon(Icons.play_arrow),
                        label: Text(
                            busy ? 'Chờ hub xác nhận…' : 'Bắt đầu buổi tập'))),
                const SizedBox(height: 12),
                const Text(
                    'Thời gian và số lần chỉ bắt đầu khi bạn sẵn sàng và lời hướng dẫn đã phát xong. Luôn có thể dừng trên màn hình Tập luyện.'),
              ])),
        ]));
  }
}

class ExerciseInstructions extends StatelessWidget {
  final String exerciseId;
  final bool both;
  const ExerciseInstructions(
      {super.key, required this.exerciseId, this.both = false});
  @override
  Widget build(BuildContext context) {
    final e = exerciseDetails(exerciseId),
        steps = (e['steps'] as List).cast<String>(),
        poses = e['illustrations'] as List;
    return Panel(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Cách tập',
          style:
              TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: ink)),
      const SizedBox(height: 12),
      for (var i = 0; i < 3; i++)
        Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SizedBox(
                  width: 90,
                  height: 115,
                  child: CustomPaint(
                      painter: ExercisePosePainter(asMap(poses[i]),
                          chair: e['chair'] == true,
                          support: e['support'] == true))),
              const SizedBox(width: 12),
              Expanded(
                  child: Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: Text('${i + 1}. ${steps[i]}',
                          style: const TextStyle(fontSize: 17, height: 1.4)))),
            ])),
      Text('Chuẩn bị: ${e['equipment']}', style: const TextStyle(height: 1.5)),
      const SizedBox(height: 12),
      Text('Vị trí webcam: ${both ? e['both_camera_text'] : e['camera_text']}',
          style: const TextStyle(fontWeight: FontWeight.w600, height: 1.5)),
      const SizedBox(height: 8),
      Text('Cần thấy: ${(e['visible_joints'] as List).join(', ')}.'),
      if (both)
        const Text(
            'Khi tập cả hai, cần thấy các khớp trên ở cả bên trái và bên phải.'),
    ]));
  }
}

class ExercisePosePainter extends CustomPainter {
  final Map<String, dynamic> pose;
  final bool chair, support;
  ExercisePosePainter(this.pose, {this.chair = false, this.support = false});
  @override
  void paint(Canvas canvas, Size size) {
    Offset point(String key) {
      final p = pose[key] as List;
      return Offset(number(p[0]).toDouble() * size.width,
          number(p[1]).toDouble() * size.height);
    }

    final body = Paint()
      ..color = green
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;
    final prop = Paint()
      ..color = const Color(0xff829c91)
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    canvas.drawRRect(
        RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(12)),
        Paint()..color = const Color(0xffe5f4ee));
    if (chair) {
      canvas.drawLine(Offset(size.width * .21, size.height * .60),
          Offset(size.width * .57, size.height * .60), prop);
      canvas.drawLine(Offset(size.width * .21, size.height * .35),
          Offset(size.width * .21, size.height * .87), prop);
      canvas.drawLine(Offset(size.width * .54, size.height * .60),
          Offset(size.width * .54, size.height * .87), prop);
    }
    if (support) {
      canvas.drawLine(Offset(size.width * .08, size.height * .46),
          Offset(size.width * .29, size.height * .46), prop);
      canvas.drawLine(Offset(size.width * .17, size.height * .46),
          Offset(size.width * .17, size.height * .91), prop);
    }
    canvas.drawLine(Offset(size.width * .1, size.height * .96),
        Offset(size.width * .96, size.height * .96), prop);
    for (final edge in [
      ['shoulder', 'hip'],
      ['shoulder', 'elbow'],
      ['elbow', 'wrist'],
      ['hip', 'knee'],
      ['knee', 'ankle'],
      ['hip', 'other_knee'],
      ['other_knee', 'other_ankle']
    ]) {
      canvas.drawLine(point(edge[0]), point(edge[1]), body);
    }
    canvas.drawCircle(point('head'), size.width * .075, Paint()..color = green);
    canvas.drawLine(
        point('head') + Offset(0, size.width * .07), point('shoulder'), body);
  }

  @override
  bool shouldRepaint(covariant ExercisePosePainter oldDelegate) =>
      oldDelegate.pose != pose ||
      oldDelegate.chair != chair ||
      oldDelegate.support != support;
}
