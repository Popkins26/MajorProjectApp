import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:intl/intl.dart';
import 'package:major_project_app/pages/select_recording_page.dart';

class TaskSchedulerPage extends StatefulWidget {
  @override
  _TaskSchedulerPageState createState() => _TaskSchedulerPageState();
}

class _TaskSchedulerPageState extends State<TaskSchedulerPage> {
  final TextEditingController _taskController = TextEditingController();
  DateTime? _selectedDateTime;
  String? _selectedRecordingUrl;
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;

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

  Future<void> _selectRecording(BuildContext context) async {
    final selectedRecording = await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => SelectRecordingPage(),
      ),
    );

    if (selectedRecording != null) {
      setState(() {
        _selectedRecordingUrl = selectedRecording;
      });
    }
  }

  void _addTask() async {
    if (_taskController.text.isEmpty || _selectedDateTime == null) return;

    await _firestore.collection('tasks').add({
      'task': _taskController.text,
      'scheduledTime': _selectedDateTime!.millisecondsSinceEpoch,
      'timestamp': Timestamp.fromMillisecondsSinceEpoch(_selectedDateTime!.millisecondsSinceEpoch),
      'recordingUrl': _selectedRecordingUrl,
    });

    _taskController.clear();
    setState(() {
      _selectedDateTime = null;
      _selectedRecordingUrl = null;
    });
  }

  void _deleteTask(String id) async {
    await _firestore.collection('tasks').doc(id).delete();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Task Scheduler')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            TextField(
              controller: _taskController,
              decoration: InputDecoration(labelText: 'Task Name'),
            ),
            SizedBox(height: 10),
            Row(
              children: [
                ElevatedButton(
                  onPressed: () => _selectDateTime(context),
                  child: Text(_selectedDateTime == null
                      ? 'Select Date & Time'
                      : DateFormat('yyyy-MM-dd HH:mm').format(_selectedDateTime!)),
                ),
                SizedBox(width: 10),
                ElevatedButton(
                  onPressed: () => _selectRecording(context),
                  child: Text(_selectedRecordingUrl == null
                      ? 'Select Recording'
                      : 'Recording Selected'),
                ),
              ],
            ),
            SizedBox(height: 10),
            ElevatedButton(
              onPressed: _addTask,
              child: Text('Schedule Task'),
            ),
            SizedBox(height: 20),
            Expanded(
              child: StreamBuilder(
                stream: _firestore.collection('tasks').orderBy('scheduledTime').snapshots(),
                builder: (context, AsyncSnapshot<QuerySnapshot> snapshot) {
                  if (!snapshot.hasData) return Center(child: CircularProgressIndicator());

                  return ListView(
                    children: snapshot.data!.docs.map((doc) {
                      Map<String, dynamic> data = doc.data() as Map<String, dynamic>;
                      DateTime taskTime = DateTime.fromMillisecondsSinceEpoch(data['scheduledTime']);
                      return ListTile(
                        title: Text(data['task']),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Scheduled: ${DateFormat('yyyy-MM-dd HH:mm').format(taskTime)}'),
                            if (data['recordingUrl'] != null)
                              TextButton(
                                onPressed: () {
                                  // Add audio player logic here
                                },
                                child: Text('Play Recording'),
                              ),
                          ],
                        ),
                        trailing: IconButton(
                          icon: Icon(Icons.delete, color: Colors.red),
                          onPressed: () => _deleteTask(doc.id),
                        ),
                      );
                    }).toList(),
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
