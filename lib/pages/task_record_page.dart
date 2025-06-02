import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:intl/intl.dart';
import 'package:major_project_app/pages/select_recording_page.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/timezone.dart' as tz;
import 'package:timezone/data/latest.dart' as tz;

class TaskSchedulerPage extends StatefulWidget {
  const TaskSchedulerPage({super.key});

  @override
  _TaskSchedulerPageState createState() => _TaskSchedulerPageState();
}

class _TaskSchedulerPageState extends State<TaskSchedulerPage> {
  final TextEditingController _taskController = TextEditingController();
  DateTime? _selectedDateTime;
  DateTime? _selectedDueTime;
  String? _selectedRecordingUrl;
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final FlutterLocalNotificationsPlugin _notifications =
      FlutterLocalNotificationsPlugin();

  // Task type selection
  String _taskType = 'no_audio'; // Default to no audio

  // Audio player variables
  final AudioPlayer _audioPlayer = AudioPlayer();
  bool _isPlaying = false;
  String? _currentlyPlayingUrl;
  Duration _duration = Duration.zero;
  Duration _position = Duration.zero;

  @override
  void initState() {
    super.initState();
    _setupAudioPlayer();
    _initializeNotifications();
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }

  Future<void> _initializeNotifications() async {
    tz.initializeTimeZones();
    const androidSettings = AndroidInitializationSettings(
      '@mipmap/ic_launcher',
    );
    const iosSettings = DarwinInitializationSettings();
    const initSettings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );
    await _notifications.initialize(initSettings);
  }

  Future<void> _scheduleNotification(
    String taskName,
    DateTime dueTime,
    String? recordingUrl,
  ) async {
    const androidDetails = AndroidNotificationDetails(
      'task_due_channel',
      'Task Due Notifications',
      channelDescription: 'Notifications for task due times',
      importance: Importance.high,
      priority: Priority.high,
    );
    const iosDetails = DarwinNotificationDetails();
    const details = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    await _notifications.zonedSchedule(
      0,
      'Task Due: $taskName',
      'Your task is due now!',
      tz.TZDateTime.from(dueTime, tz.local),
      details,
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      matchDateTimeComponents: DateTimeComponents.time,
    );
  }

  void _setupAudioPlayer() {
    // Listen to audio duration changes
    _audioPlayer.onDurationChanged.listen((newDuration) {
      setState(() => _duration = newDuration);
    });

    // Listen to audio position changes
    _audioPlayer.onPositionChanged.listen((newPosition) {
      setState(() => _position = newPosition);
    });

    // Listen to player state changes
    _audioPlayer.onPlayerComplete.listen((event) {
      setState(() {
        _isPlaying = false;
        _position = Duration.zero;
      });
    });
  }

  void _selectDateTime(BuildContext context) async {
    DateTime? pickedDate = await showDatePicker(
      context: context,
      initialDate: DateTime.now(),
      firstDate: DateTime.now(),
      lastDate: DateTime(2101),
    );

    if (pickedDate != null) {
      TimeOfDay? pickedTime = await showTimePicker(
        context: context,
        initialTime: TimeOfDay.now(),
      );

      if (pickedTime != null) {
        setState(() {
          _selectedDateTime = DateTime(
            pickedDate.year,
            pickedDate.month,
            pickedDate.day,
            pickedTime.hour,
            pickedTime.minute,
          );
        });
      }
    }
  }

  void _selectDueTime(BuildContext context) async {
    DateTime? pickedDate = await showDatePicker(
      context: context,
      initialDate: _selectedDateTime ?? DateTime.now(),
      firstDate: _selectedDateTime ?? DateTime.now(),
      lastDate: DateTime(2101),
    );

    if (pickedDate != null) {
      TimeOfDay? pickedTime = await showTimePicker(
        context: context,
        initialTime: TimeOfDay.now(),
      );

      if (pickedTime != null) {
        setState(() {
          _selectedDueTime = DateTime(
            pickedDate.year,
            pickedDate.month,
            pickedDate.day,
            pickedTime.hour,
            pickedTime.minute,
          );
        });
      }
    }
  }

  Future<void> _selectRecording(BuildContext context) async {
    final selectedRecording = await Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => SelectRecordingPage()),
    );

    if (selectedRecording != null) {
      setState(() {
        _selectedRecordingUrl = selectedRecording;
      });
    }
  }

  void _addTask() async {
    if (_taskController.text.isEmpty || _selectedDateTime == null) return;

    // Validate audio selection if task type is with audio
    if (_taskType == 'with_audio' && _selectedRecordingUrl == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please select an audio file for this task'),
        ),
      );
      return;
    }

    try {
      final taskData = {
        'task': _taskController.text,
        'scheduledTime': _selectedDateTime!.millisecondsSinceEpoch,
        'timestamp': Timestamp.fromMillisecondsSinceEpoch(
          _selectedDateTime!.millisecondsSinceEpoch,
        ),
        'isCompleted': false,
        'taskType': _taskType, // Add task type to the data
      };

      // Add recording URL if task type is with audio
      if (_taskType == 'with_audio' && _selectedRecordingUrl != null) {
        taskData['recordingUrl'] = _selectedRecordingUrl as String;
      }

      // Add due time if selected
      if (_selectedDueTime != null) {
        taskData['dueTime'] = _selectedDueTime!.millisecondsSinceEpoch;

        // Schedule notification for due time
        try {
          await _scheduleNotification(
            _taskController.text,
            _selectedDueTime!,
            _selectedRecordingUrl,
          );
        } catch (e) {
          print('Error scheduling notification: $e');
          // Continue with task creation even if notification fails
        }
      }

      await _firestore.collection('tasks').add(taskData);

      _taskController.clear();
      setState(() {
        _selectedDateTime = null;
        _selectedDueTime = null;
        _selectedRecordingUrl = null;
        _taskType = 'no_audio'; // Reset to default
      });

      // Show success message
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Task added successfully')),
        );
      }
    } catch (e) {
      print('Error adding task: $e');
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Error adding task: $e')));
      }
    }
  }

  void _deleteTask(String id) async {
    await _firestore.collection('tasks').doc(id).delete();
  }

  Future<void> _playRecording(String url) async {
    try {
      if (_isPlaying && _currentlyPlayingUrl == url) {
        await _audioPlayer.pause();
        setState(() {
          _isPlaying = false;
        });
      } else {
        await _audioPlayer.stop();
        await _audioPlayer.play(UrlSource(url));
        setState(() {
          _isPlaying = true;
          _currentlyPlayingUrl = url;
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Error playing audio: $e')));
    }
  }

  String _formatDuration(Duration duration) {
    String twoDigits(int n) => n.toString().padLeft(2, '0');
    final hours = twoDigits(duration.inHours);
    final minutes = twoDigits(duration.inMinutes.remainder(60));
    final seconds = twoDigits(duration.inSeconds.remainder(60));
    return [if (duration.inHours > 0) hours, minutes, seconds].join(':');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Task Scheduler',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.white,
        elevation: 0.5,
        iconTheme: const IconThemeData(color: Colors.black87),
        titleTextStyle: const TextStyle(
          color: Colors.black87,
          fontWeight: FontWeight.bold,
          fontSize: 20,
        ),
      ),
      body: Container(
        color: const Color(0xFFF5F5F5),
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(12.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Task Scheduler',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                SizedBox(height: 12),
                Card(
                  elevation: 2,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(12.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // Task Name Input
                        TextField(
                          controller: _taskController,
                          decoration: InputDecoration(
                            labelText: 'Task Name',
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                            contentPadding: EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 8,
                            ),
                          ),
                        ),
                        SizedBox(height: 12),

                        // Task Type Selection
                        Text('Task Type:', style: TextStyle(fontSize: 14)),
                        Row(
                          children: [
                            Radio<String>(
                              value: 'no_audio',
                              groupValue: _taskType,
                              onChanged: (value) {
                                setState(() {
                                  _taskType = value!;
                                  if (value == 'no_audio') {
                                    _selectedRecordingUrl = null;
                                  }
                                });
                              },
                              materialTapTargetSize:
                                  MaterialTapTargetSize.shrinkWrap,
                            ),
                            Text(
                              'Without Audio',
                              style: TextStyle(fontSize: 14),
                            ),
                            SizedBox(width: 16),
                            Radio<String>(
                              value: 'with_audio',
                              groupValue: _taskType,
                              onChanged: (value) {
                                setState(() {
                                  _taskType = value!;
                                });
                              },
                              materialTapTargetSize:
                                  MaterialTapTargetSize.shrinkWrap,
                            ),
                            Text('With Audio', style: TextStyle(fontSize: 14)),
                          ],
                        ),
                        SizedBox(height: 8),

                        // Date & Time Selection
                        Container(
                          decoration: BoxDecoration(
                            color: Colors.grey[100],
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: ListTile(
                            leading: Icon(
                              Icons.calendar_today,
                              size: 20,
                              color: Theme.of(context).primaryColor,
                            ),
                            title: Text(
                              _selectedDateTime == null
                                  ? 'Select Date & Time'
                                  : DateFormat(
                                    'yyyy-MM-dd HH:mm',
                                  ).format(_selectedDateTime!),
                              style: TextStyle(fontSize: 14),
                            ),
                            contentPadding: EdgeInsets.symmetric(
                              horizontal: 12,
                            ),
                            onTap: () => _selectDateTime(context),
                          ),
                        ),
                        SizedBox(height: 8),

                        // Audio Selection (if with_audio is selected)
                        if (_taskType == 'with_audio')
                          Container(
                            decoration: BoxDecoration(
                              color: Colors.grey[100],
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: ListTile(
                              leading: Icon(
                                Icons.audio_file,
                                size: 20,
                                color: Theme.of(context).primaryColor,
                              ),
                              title: Text(
                                _selectedRecordingUrl == null
                                    ? 'Select Recording'
                                    : 'Recording Selected',
                                style: TextStyle(fontSize: 14),
                              ),
                              contentPadding: EdgeInsets.symmetric(
                                horizontal: 12,
                              ),
                              onTap: () => _selectRecording(context),
                            ),
                          ),

                        SizedBox(height: 8),

                        // Due Time Selection
                        Container(
                          decoration: BoxDecoration(
                            color: Colors.grey[100],
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: ListTile(
                            leading: Icon(
                              Icons.timer,
                              size: 20,
                              color: Theme.of(context).primaryColor,
                            ),
                            title: Text(
                              _selectedDueTime == null
                                  ? 'Add Due Time (Optional)'
                                  : 'Due: ${DateFormat('yyyy-MM-dd HH:mm').format(_selectedDueTime!)}',
                              style: TextStyle(fontSize: 14),
                            ),
                            contentPadding: EdgeInsets.symmetric(
                              horizontal: 12,
                            ),
                            onTap: () => _selectDueTime(context),
                          ),
                        ),
                        SizedBox(height: 12),

                        // Schedule Task Button
                        ElevatedButton(
                          onPressed: _addTask,
                          child: Text(
                            'Schedule Task',
                            style: TextStyle(fontSize: 14),
                          ),
                          style: ElevatedButton.styleFrom(
                            padding: EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                SizedBox(height: 12),
                // Task List remains the same but with updated styling for compactness
                Padding(
                  padding: const EdgeInsets.only(
                    bottom: 60,
                  ), // Add padding for bottom navigation
                  child: StreamBuilder(
                    stream:
                        _firestore
                            .collection('tasks')
                            .orderBy('scheduledTime')
                            .snapshots(),
                    builder: (context, AsyncSnapshot<QuerySnapshot> snapshot) {
                      if (!snapshot.hasData)
                        return Center(child: CircularProgressIndicator());

                      if (snapshot.data!.docs.isEmpty) {
                        return Center(
                          child: Text(
                            'No tasks scheduled yet',
                            style: TextStyle(fontSize: 14),
                          ),
                        );
                      }

                      return ListView.builder(
                        shrinkWrap: true,
                        physics: NeverScrollableScrollPhysics(),
                        itemCount: snapshot.data!.docs.length,
                        itemBuilder: (context, index) {
                          DocumentSnapshot doc = snapshot.data!.docs[index];
                          Map<String, dynamic> data =
                              doc.data() as Map<String, dynamic>;
                          DateTime taskTime =
                              DateTime.fromMillisecondsSinceEpoch(
                                data['scheduledTime'],
                              );
                          String? recordingUrl = data['recordingUrl'];
                          bool isThisPlaying =
                              _isPlaying &&
                              _currentlyPlayingUrl == recordingUrl;
                          bool isCompleted = data['isCompleted'] ?? false;
                          String taskType = data['taskType'] ?? 'no_audio';

                          return Card(
                            margin: EdgeInsets.only(bottom: 8),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.all(8.0),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Expanded(
                                        child: Text(
                                          data['task'],
                                          style: TextStyle(
                                            fontSize: 14,
                                            fontWeight: FontWeight.bold,
                                            decoration:
                                                isCompleted
                                                    ? TextDecoration.lineThrough
                                                    : null,
                                          ),
                                        ),
                                      ),
                                      if (taskType == 'with_audio')
                                        Icon(
                                          Icons.audio_file,
                                          color: Colors.blue,
                                          size: 16,
                                        ),
                                      SizedBox(width: 4),
                                      Checkbox(
                                        value: isCompleted,
                                        onChanged: (bool? value) async {
                                          await _firestore
                                              .collection('tasks')
                                              .doc(doc.id)
                                              .update({'isCompleted': value});
                                        },
                                        materialTapTargetSize:
                                            MaterialTapTargetSize.shrinkWrap,
                                      ),
                                      IconButton(
                                        icon: Icon(
                                          Icons.delete,
                                          color: Colors.red,
                                          size: 20,
                                        ),
                                        onPressed: () => _deleteTask(doc.id),
                                        padding: EdgeInsets.zero,
                                        constraints: BoxConstraints(),
                                      ),
                                    ],
                                  ),
                                  if (recordingUrl != null) ...[
                                    Row(
                                      children: [
                                        IconButton(
                                          icon: Icon(
                                            isThisPlaying
                                                ? Icons.pause
                                                : Icons.play_arrow,
                                            size: 20,
                                            color:
                                                Theme.of(context).primaryColor,
                                          ),
                                          onPressed:
                                              () =>
                                                  _playRecording(recordingUrl),
                                          padding: EdgeInsets.zero,
                                          constraints: BoxConstraints(),
                                        ),
                                        SizedBox(width: 8),
                                        Expanded(
                                          child: Column(
                                            children: [
                                              SliderTheme(
                                                data: SliderTheme.of(
                                                  context,
                                                ).copyWith(
                                                  activeTrackColor:
                                                      Theme.of(
                                                        context,
                                                      ).primaryColor,
                                                  thumbColor:
                                                      Theme.of(
                                                        context,
                                                      ).primaryColor,
                                                ),
                                                child: Slider(
                                                  value:
                                                      _position.inSeconds
                                                          .toDouble(),
                                                  min: 0,
                                                  max:
                                                      _duration.inSeconds
                                                          .toDouble(),
                                                  onChanged: (value) async {
                                                    final position = Duration(
                                                      seconds: value.toInt(),
                                                    );
                                                    await _audioPlayer.seek(
                                                      position,
                                                    );
                                                  },
                                                ),
                                              ),
                                              Padding(
                                                padding:
                                                    const EdgeInsets.symmetric(
                                                      horizontal: 8,
                                                    ),
                                                child: Row(
                                                  mainAxisAlignment:
                                                      MainAxisAlignment
                                                          .spaceBetween,
                                                  children: [
                                                    Text(
                                                      _formatDuration(
                                                        _position,
                                                      ),
                                                      style: TextStyle(
                                                        fontSize: 12,
                                                      ),
                                                    ),
                                                    Text(
                                                      _formatDuration(
                                                        _duration,
                                                      ),
                                                      style: TextStyle(
                                                        fontSize: 12,
                                                      ),
                                                    ),
                                                  ],
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          );
                        },
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
