import 'dart:io';
import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';

class VoiceRecorderPage extends StatefulWidget {
  const VoiceRecorderPage({super.key});

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

  // Audio player variables
  Duration _duration = Duration.zero;
  Duration _position = Duration.zero;

  @override
  void initState() {
    super.initState();
    _initDirectory();
    _setupAudioPlayer();
  }

  @override
  void dispose() {
    _recorder.dispose();
    _audioPlayer.dispose();
    super.dispose();
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

  Future<void> _initDirectory() async {
    _appDirectory = await getApplicationDocumentsDirectory();
    await _loadRecordings();
  }

  Future<void> _startRecording() async {
    if (_appDirectory == null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Storage not available')));
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
    TextEditingController controller = TextEditingController(
      text: "Recording_${DateTime.now().millisecondsSinceEpoch}",
    );
    DateTime? selectedDateTime;

    showDialog(
      context: context,
      builder:
          (context) => StatefulBuilder(
            builder:
                (context, setState) => AlertDialog(
                  title: Text('Edit Recording Name'),
                  content: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      TextField(
                        controller: controller,
                        decoration: InputDecoration(
                          labelText: 'Recording Name',
                        ),
                      ),
                      SizedBox(height: 16),
                      ElevatedButton.icon(
                        icon: Icon(Icons.calendar_today),
                        label: Text(
                          selectedDateTime == null
                              ? 'Select Date & Time (Optional)'
                              : selectedDateTime.toString(),
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
                        String name = controller.text.trim();
                        if (name.isNotEmpty) {
                          await _uploadToStorageAndSaveToFirestore(
                            name,
                            filePath,
                            selectedDateTime ?? DateTime.now(),
                          );
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Name is required')),
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
    String name,
    String filePath,
    DateTime scheduledTime,
  ) async {
    try {
      File file = File(filePath);
      String storagePath = 'recordings/$name.mp3';

      // Set metadata with the correct content type
      SettableMetadata metadata = SettableMetadata(contentType: 'audio/mpeg');

      TaskSnapshot uploadTask = await FirebaseStorage.instance
          .ref(storagePath)
          .putFile(file, metadata);

      String downloadUrl = await uploadTask.ref.getDownloadURL();

      // Create Firestore document with optional scheduledTime
      Map<String, dynamic> firestoreData = {
        'name': name,
        'storagePath': storagePath,
        'downloadUrl': downloadUrl,
        'timestamp': FieldValue.serverTimestamp(),
      };

      // Only add scheduledTime if it's different from current time
      if (scheduledTime.difference(DateTime.now()).inMinutes.abs() > 1) {
        firestoreData['scheduledTime'] = scheduledTime.millisecondsSinceEpoch;
      }

      DocumentReference docRef = await FirebaseFirestore.instance
          .collection('recordings')
          .add(firestoreData);

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
        SnackBar(
          content: Text('Uploaded to Firebase Storage and saved to Firestore!'),
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Error uploading: $e')));
    }
  }

  Future<void> _playRecording(String downloadUrl) async {
    try {
      if (_isPlaying && _currentlyPlayingFile == downloadUrl) {
        await _audioPlayer.pause();
        setState(() {
          _isPlaying = false;
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
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Error playing audio: $e')));
    }
  }

  String _formatDuration(Duration duration) {
    String twoDigits(int n) => n.toString().padLeft(2, '0');
    final minutes = twoDigits(duration.inMinutes.remainder(60));
    final seconds = twoDigits(duration.inSeconds.remainder(60));
    return '$minutes:$seconds';
  }

  Future<void> _loadRecordings() async {
    try {
      // Get recordings from Firebase Storage
      final storageRef = FirebaseStorage.instance.ref('recordings/');
      final result = await storageRef.listAll();

      // Get Firestore documents for these recordings
      QuerySnapshot snapshot =
          await FirebaseFirestore.instance
              .collection('recordings')
              .orderBy('timestamp', descending: true)
              .get();

      // Create a map of storage paths to Firestore data
      Map<String, Map<String, dynamic>> firestoreData = {};
      for (var doc in snapshot.docs) {
        final data = doc.data() as Map<String, dynamic>;
        if (data['storagePath'] != null) {
          firestoreData[data['storagePath']] = {
            'id': doc.id,
            'name': data['name'] ?? 'Unnamed Recording',
            'downloadUrl': data['downloadUrl'],
            'scheduledTime': data['scheduledTime'],
          };
        }
      }

      // Combine Storage and Firestore data
      List<Map<String, dynamic>> recordings = [];
      for (var item in result.items) {
        final path = item.fullPath;
        if (firestoreData.containsKey(path)) {
          recordings.add(firestoreData[path]!);
        }
      }

      setState(() {
        _recordings = recordings;
      });
    } catch (e) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Error loading recordings: $e')));
    }
  }

  Future<void> _deleteRecording(
    Map<String, dynamic> recording,
    int index,
  ) async {
    try {
      // Attempt to delete the file from Firebase Storage
      final storageRef = FirebaseStorage.instance.ref(recording['path']);
      await storageRef.delete();
    } catch (e) {
      // Handle the case where the file does not exist in Firebase Storage
      if (e is FirebaseException && e.code == 'object-not-found') {
        print(
          'File not found in Firebase Storage, proceeding to delete Firestore document.',
        );
      } else {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Error deleting file: $e')));
        return; // Exit if the error is not related to a missing file
      }
    }

    try {
      // Delete the Firestore document
      final docRef = FirebaseFirestore.instance
          .collection('recordings')
          .doc(recording['id']);
      await docRef.delete();

      // Remove the recording from the local list
      setState(() {
        _recordings.removeAt(index);
      });

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Recording deleted successfully')));
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error deleting Firestore document: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Voice Recorder',
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
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            children: [
              // Recording controls
              Card(
                elevation: 4,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(20.0),
                  child: Column(
                    children: [
                      CircleAvatar(
                        radius: 40,
                        backgroundColor:
                            _isRecording
                                ? Colors.red[400]
                                : Theme.of(
                                  context,
                                ).primaryColor.withOpacity(0.15),
                        child: IconButton(
                          icon: Icon(
                            _isRecording ? Icons.stop : Icons.mic,
                            color:
                                _isRecording ? Colors.white : Colors.deepPurple,
                            size: 32,
                          ),
                          onPressed:
                              _isRecording ? _stopRecording : _startRecording,
                        ),
                      ),
                      const SizedBox(height: 16),
                      Text(
                        _isRecording ? 'Recording...' : 'Tap to Record',
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.black87,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              // Recordings list
              Expanded(
                child:
                    _recordings.isEmpty
                        ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.mic_none,
                                size: 64,
                                color: Colors.grey[400],
                              ),
                              const SizedBox(height: 16),
                              const Text(
                                'No recordings yet',
                                style: TextStyle(
                                  fontSize: 18,
                                  color: Colors.black54,
                                ),
                              ),
                            ],
                          ),
                        )
                        : ListView.builder(
                          itemCount: _recordings.length,
                          itemBuilder: (context, index) {
                            Map<String, dynamic> recording = _recordings[index];
                            bool isThisPlaying =
                                _isPlaying &&
                                _currentlyPlayingFile ==
                                    recording['downloadUrl'];
                            return Card(
                              elevation: 4,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(18),
                              ),
                              margin: const EdgeInsets.symmetric(vertical: 10),
                              child: Padding(
                                padding: const EdgeInsets.all(18.0),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        CircleAvatar(
                                          backgroundColor: Theme.of(
                                            context,
                                          ).primaryColor.withOpacity(0.10),
                                          child: const Icon(
                                            Icons.mic,
                                            color: Colors.deepPurple,
                                          ),
                                        ),
                                        const SizedBox(width: 12),
                                        Expanded(
                                          child: Text(
                                            recording['name'],
                                            style: const TextStyle(
                                              fontWeight: FontWeight.bold,
                                              fontSize: 18,
                                              color: Colors.black87,
                                            ),
                                          ),
                                        ),
                                        IconButton(
                                          icon: const Icon(
                                            Icons.delete_outline,
                                            color: Colors.redAccent,
                                          ),
                                          onPressed:
                                              () => _deleteRecording(
                                                recording,
                                                index,
                                              ),
                                          tooltip: 'Delete',
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 8),
                                    Row(
                                      children: [
                                        IconButton(
                                          icon: Icon(
                                            isThisPlaying
                                                ? Icons.pause_circle_filled
                                                : Icons.play_circle_filled,
                                            color:
                                                Theme.of(context).primaryColor,
                                            size: 36,
                                          ),
                                          onPressed:
                                              () => _playRecording(
                                                recording['downloadUrl'],
                                              ),
                                          tooltip:
                                              isThisPlaying ? 'Pause' : 'Play',
                                        ),
                                        Expanded(
                                          child: Slider(
                                            value:
                                                isThisPlaying
                                                    ? _position.inMilliseconds
                                                        .toDouble()
                                                    : 0,
                                            min: 0,
                                            max:
                                                isThisPlaying
                                                    ? _duration.inMilliseconds
                                                        .toDouble()
                                                    : 1,
                                            onChanged:
                                                isThisPlaying
                                                    ? (value) {
                                                      _audioPlayer.seek(
                                                        Duration(
                                                          milliseconds:
                                                              value.round(),
                                                        ),
                                                      );
                                                    }
                                                    : null,
                                            activeColor:
                                                Theme.of(context).primaryColor,
                                            inactiveColor: Colors.grey[300],
                                          ),
                                        ),
                                        Text(
                                          isThisPlaying
                                              ? _formatDuration(_position)
                                              : '00:00',
                                          style: const TextStyle(
                                            fontFamily: 'monospace',
                                            color: Colors.black54,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                            );
                          },
                        ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
