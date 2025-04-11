import 'dart:io';
import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';

class VoiceRecorderPage extends StatefulWidget {
  @override
  _VoiceRecorderPageState createState() => _VoiceRecorderPageState();
}

class _VoiceRecorderPageState extends State<VoiceRecorderPage> {
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _audioPlayer = AudioPlayer();
  bool _isRecording = false;
  bool _isPlaying = false;
  String? _currentlyPlayingFile;
  List<Map<String, dynamic>> _recordings = [];
  Directory? _appDirectory;

  @override
  void initState() {
    super.initState();
    _initDirectory();
  }

  @override
  void dispose() {
    _recorder.dispose();
    super.dispose();
  }

  Future<void> _initDirectory() async {
    _appDirectory = await getApplicationDocumentsDirectory();
    await _loadRecordings();
  }

  Future<void> _startRecording() async {
    if (_appDirectory == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Storage not available')),
      );
      return;
    }

    if (await _recorder.hasPermission()) {
      String filePath =
          '${_appDirectory!.path}/${DateTime.now().millisecondsSinceEpoch}.mp3';
      await _recorder.start(const RecordConfig(), path: filePath);
      setState(() => _isRecording = true);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Recording permission not granted')),
      );
    }
  }

  Future<void> _stopRecording() async {
    final filePath = await _recorder.stop();
    if (filePath != null && filePath.isNotEmpty) {
      setState(() => _isRecording = false);
      _showEditNameDialog(filePath);
    }
  }

  void _showEditNameDialog(String filePath) {
    TextEditingController _controller = TextEditingController(
      text: "Recording_${DateTime.now().millisecondsSinceEpoch}",
    );
    DateTime? selectedDateTime;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: Text('Edit Recording Name'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _controller,
                decoration: InputDecoration(labelText: 'Recording Name'),
              ),
              SizedBox(height: 16),
              ElevatedButton.icon(
                icon: Icon(Icons.calendar_today),
                label: Text(
                  selectedDateTime == null
                      ? 'Select Date & Time'
                      : '${selectedDateTime.toString()}',
                ),
                onPressed: () async {
                  DateTime? pickedDate = await showDatePicker(
                    context: context,
                    initialDate: DateTime.now(),
                    firstDate: DateTime.now(),
                    lastDate: DateTime(2100),
                  );
                  if (pickedDate != null) {
                    TimeOfDay? pickedTime = await showTimePicker(
                      context: context,
                      initialTime: TimeOfDay.now(),
                    );
                    if (pickedTime != null) {
                      setState(() {
                        selectedDateTime = DateTime(
                          pickedDate.year,
                          pickedDate.month,
                          pickedDate.day,
                          pickedTime.hour,
                          pickedTime.minute,
                        );
                      });
                    }
                  }
                },
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text('Cancel'),
            ),
            TextButton(
              onPressed: () async {
                String name = _controller.text.trim();
                if (name.isNotEmpty && selectedDateTime != null) {
                  await _uploadToStorageAndSaveToFirestore(
                      name, filePath, selectedDateTime!);
                } else {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Name & time must be selected')),
                  );
                }
                Navigator.pop(context);
              },
              child: Text('Save & Upload'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _uploadToStorageAndSaveToFirestore(
      String name, String filePath, DateTime scheduledTime) async {
    try {
      File file = File(filePath);
      String storagePath = 'recordings/$name.mp3';

      TaskSnapshot uploadTask =
          await FirebaseStorage.instance.ref(storagePath).putFile(file);

      String downloadUrl = await uploadTask.ref.getDownloadURL();

      DocumentReference docRef =
          await FirebaseFirestore.instance.collection('recordings').add({
        'name': name,
        'storagePath': storagePath,
        'downloadUrl': downloadUrl,
        'scheduledTime': scheduledTime.millisecondsSinceEpoch,
        'timestamp': Timestamp.fromMillisecondsSinceEpoch(scheduledTime.millisecondsSinceEpoch),
      });

      setState(() {
        _recordings.insert(0, {
          'id': docRef.id,
          'path': storagePath,
          'name': name,
          'downloadUrl': downloadUrl,
          'scheduledTime': scheduledTime,
        });
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Uploaded to Firebase Storage and saved to Firestore!')),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error uploading: $e')),
      );
    }
  }

  Future<void> _playRecording(String downloadUrl) async {
    try {
      if (_isPlaying && _currentlyPlayingFile == downloadUrl) {
        await _audioPlayer.stop();
        setState(() {
          _isPlaying = false;
          _currentlyPlayingFile = null;
        });
      } else {
        await _audioPlayer.stop();
        await _audioPlayer.play(UrlSource(downloadUrl));
        setState(() {
          _isPlaying = true;
          _currentlyPlayingFile = downloadUrl;
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error playing audio: $e')),
      );
    }
  }

  Future<void> _loadRecordings() async {
    try {
      QuerySnapshot snapshot = await FirebaseFirestore.instance
          .collection('recordings')
          .orderBy('timestamp', descending: true)
          .get();

      setState(() {
        _recordings = snapshot.docs.map((doc) {
          final data = doc.data() as Map<String, dynamic>;
          return {
            'id': doc.id,
            'path': data['storagePath'] ?? '',
            'name': data['name'] ?? 'Unnamed Recording',
            'downloadUrl': data['downloadUrl'],
          };
        }).toList();
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading recordings: $e')),
      );
    }
  }

  Future<void> _deleteRecording(Map<String, dynamic> recording, int index) async {
    try {
      final storageRef = FirebaseStorage.instance.ref(recording['path']);
      await storageRef.delete();

      final docRef = FirebaseFirestore.instance.collection('recordings').doc(recording['id']);
      await docRef.delete();

      setState(() {
        _recordings.removeAt(index);
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Recording deleted successfully')),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error deleting recording: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Voice Recorder')),
      body: Padding(
        padding: EdgeInsets.all(16.0),
        child: Column(
          children: [
            CircleAvatar(
              radius: 40,
              backgroundColor: _isRecording ? Colors.red : Colors.green,
              child: IconButton(
                icon: Icon(
                  _isRecording ? Icons.stop : Icons.mic,
                  color: Colors.white,
                ),
                onPressed: _isRecording ? _stopRecording : _startRecording,
              ),
            ),
            SizedBox(height: 20),
            Expanded(
              child: ListView.builder(
                itemCount: _recordings.length,
                itemBuilder: (context, index) {
                  Map<String, dynamic> recording = _recordings[index];
                  return Card(
                    child: ListTile(
                      title: Text(recording['name']),
                      leading: IconButton(
                        icon: Icon(
                          _currentlyPlayingFile == recording['downloadUrl']
                              ? Icons.pause
                              : Icons.play_arrow,
                        ),
                        onPressed: () =>
                            _playRecording(recording['downloadUrl']),
                      ),
                      trailing: IconButton(
                        icon: Icon(Icons.delete, color: Colors.red),
                        onPressed: () =>
                            _deleteRecording(recording, index),
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
