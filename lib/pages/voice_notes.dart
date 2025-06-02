import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:rxdart/rxdart.dart';

class VoiceNotesPage extends StatefulWidget {
  @override
  _VoiceNotesPageState createState() => _VoiceNotesPageState();
}

class _VoiceNotesPageState extends State<VoiceNotesPage> {
  final AudioPlayer _audioPlayer = AudioPlayer();
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final FirebaseStorage _storage = FirebaseStorage.instance;

  String? _currentPlayingId;
  bool _isPlaying = false;
  Duration _duration = Duration.zero;
  Duration _position = Duration.zero;
  double _currentSliderValue = 0.0;
  List<Map<String, dynamic>> _voiceNotes = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _setupAudioPlayer();
    _fetchVoiceNotes();
  }

  void _setupAudioPlayer() {
    _audioPlayer.onDurationChanged.listen((Duration d) {
      setState(() => _duration = d);
    });

    _audioPlayer.onPositionChanged.listen((Duration p) {
      setState(() {
        _position = p;
        _currentSliderValue = p.inMilliseconds.toDouble();
      });
    });

    _audioPlayer.onPlayerComplete.listen((_) {
      setState(() {
        _isPlaying = false;
        _position = Duration.zero;
        _currentSliderValue = 0;
      });
    });
  }

  Future<void> _fetchVoiceNotes() async {
    try {
      setState(() => _isLoading = true);

      final storageRef = _storage.ref().child('voice_notes');
      final ListResult result = await storageRef.listAll();

      final notes = await Future.wait(
        result.items.map((Reference ref) async {
          final String url = await ref.getDownloadURL();
          final String fileName = ref.name;
          return {
            'id': fileName,
            'title': fileName,
            'url': url,
            'timestamp': DateTime.now(),
          };
        }),
      );

      setState(() {
        _voiceNotes = notes;
        _isLoading = false;
      });
    } catch (e, stack) {
      print('Error fetching voice notes: $e');
      print(stack);
      setState(() {
        _voiceNotes = [];
        _isLoading = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to load voice notes: \\n$e'),
            duration: Duration(seconds: 5),
          ),
        );
      }
    }
  }

  Future<void> _deleteVoiceNote(String id, String url) async {
    try {
      if (_currentPlayingId == id) {
        await _audioPlayer.stop();
        setState(() {
          _isPlaying = false;
          _currentPlayingId = null;
        });
      }

      // Delete from Firebase Storage
      final storageRef = _storage.ref().child('voice_notes/$id');
      await storageRef.delete();

      setState(() {
        _voiceNotes.removeWhere((note) => note['id'] == id);
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Voice note deleted successfully')),
      );
    } catch (e) {
      print('Error deleting voice note: $e');
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Failed to delete voice note')));
    }
  }

  Future<void> _playPauseAudio(String id, String url) async {
    try {
      if (_currentPlayingId != id) {
        await _audioPlayer.stop();
        await _audioPlayer.setSource(UrlSource(url));
        await _audioPlayer.resume();
        setState(() {
          _currentPlayingId = id;
          _isPlaying = true;
        });
      } else {
        if (_isPlaying) {
          await _audioPlayer.pause();
        } else {
          await _audioPlayer.resume();
        }
        setState(() => _isPlaying = !_isPlaying);
      }
    } catch (e) {
      print('Error playing audio: $e');
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Failed to play audio')));
    }
  }

  String _formatDuration(Duration duration) {
    String twoDigits(int n) => n.toString().padLeft(2, '0');
    final minutes = twoDigits(duration.inMinutes.remainder(60));
    final seconds = twoDigits(duration.inSeconds.remainder(60));
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Voice Notes',
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
      floatingActionButton: FloatingActionButton(
        onPressed: _fetchVoiceNotes,
        backgroundColor: Theme.of(context).primaryColor,
        child: const Icon(Icons.refresh),
        tooltip: 'Refresh',
      ),
      body: Container(
        color: const Color(0xFFF5F5F5),
        child:
            _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _voiceNotes.isEmpty
                ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.mic_none, size: 64, color: Colors.grey[400]),
                      const SizedBox(height: 16),
                      const Text(
                        'No voice notes yet',
                        style: TextStyle(fontSize: 20, color: Colors.black54),
                      ),
                    ],
                  ),
                )
                : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _voiceNotes.length,
                  itemBuilder: (context, index) {
                    final note = _voiceNotes[index];
                    final isCurrentlyPlaying = _currentPlayingId == note['id'];
                    return Card(
                      elevation: 4,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                      margin: const EdgeInsets.symmetric(vertical: 10),
                      child: Padding(
                        padding: const EdgeInsets.all(18),
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
                                    note['title'],
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
                                      () => _deleteVoiceNote(
                                        note['id'],
                                        note['url'],
                                      ),
                                  tooltip: 'Delete',
                                ),
                              ],
                            ),
                            if (isCurrentlyPlaying) ...[
                              Slider(
                                value: _currentSliderValue,
                                min: 0,
                                max:
                                    _duration.inMilliseconds.toDouble() > 0
                                        ? _duration.inMilliseconds.toDouble()
                                        : 1,
                                onChanged: (value) {
                                  setState(() => _currentSliderValue = value);
                                  _audioPlayer.seek(
                                    Duration(milliseconds: value.round()),
                                  );
                                },
                                activeColor: Theme.of(context).primaryColor,
                                inactiveColor: Colors.grey[300],
                              ),
                              Padding(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                ),
                                child: Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      _formatDuration(_position),
                                      style: const TextStyle(
                                        fontFamily: 'monospace',
                                        color: Colors.black54,
                                      ),
                                    ),
                                    Text(
                                      _formatDuration(_duration),
                                      style: const TextStyle(
                                        fontFamily: 'monospace',
                                        color: Colors.black54,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                            const SizedBox(height: 8),
                            Center(
                              child: IconButton(
                                icon: Icon(
                                  isCurrentlyPlaying && _isPlaying
                                      ? Icons.pause_circle_filled
                                      : Icons.play_circle_filled,
                                  size: 54,
                                  color: Theme.of(context).primaryColor,
                                ),
                                onPressed:
                                    () => _playPauseAudio(
                                      note['id'],
                                      note['url'],
                                    ),
                                tooltip:
                                    isCurrentlyPlaying && _isPlaying
                                        ? 'Pause'
                                        : 'Play',
                              ),
                            ),
                            if (note['timestamp'] != null)
                              Padding(
                                padding: const EdgeInsets.only(
                                  top: 8.0,
                                  left: 4.0,
                                ),
                                child: Text(
                                  'Uploaded: ' +
                                      (note['timestamp'] is DateTime
                                          ? (note['timestamp'] as DateTime)
                                              .toLocal()
                                              .toString()
                                              .substring(0, 16)
                                          : note['timestamp'].toString()),
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: Colors.black38,
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
      ),
    );
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }
}
