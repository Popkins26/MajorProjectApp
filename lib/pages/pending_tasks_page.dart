import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:intl/intl.dart';

class PendingTasksPage extends StatefulWidget {
  @override
  _PendingTasksPageState createState() => _PendingTasksPageState();
}

class _PendingTasksPageState extends State<PendingTasksPage> {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;

  // Send a reminder to the Raspberry Pi by updating Firestore
  Future<void> _sendReminderToPi(String taskName, int scheduledTime) async {
    try {
      await _firestore.collection('reminder').doc('current').set({
        'task': taskName,
        'scheduledTime': scheduledTime, // Unix timestamp
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Reminder sent to Raspberry Pi for task: $taskName')),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error sending reminder: $e')),
      );
    }
  }

  // Simulate marking a task as done
  Future<void> _markTaskAsDone(String taskId) async {
    try {
      await _firestore.collection('tasks').doc(taskId).update({'status': 'done'});
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Task marked as done!')),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error updating task: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Pending Tasks')),
      body: StreamBuilder(
        stream: _firestore.collection('tasks').orderBy('scheduledTime').snapshots(),
        builder: (context, AsyncSnapshot<QuerySnapshot> snapshot) {
          if (!snapshot.hasData) return Center(child: CircularProgressIndicator());

          final tasks = snapshot.data!.docs;

          if (tasks.isEmpty) {
            return Center(child: Text('No pending tasks.'));
          }

          return ListView.builder(
            itemCount: tasks.length,
            itemBuilder: (context, index) {
              final task = tasks[index];
              final data = task.data() as Map<String, dynamic>;
              final taskId = task.id;
              final taskName = data['task'];
              final scheduledTime = data['scheduledTime']; // Unix timestamp
              final timestamp = data['timestamp']; // Formatted string
              final taskStatus = data['status'] ?? 'pending';

              // Convert Unix timestamp to DateTime
              final taskDateTime = DateTime.fromMillisecondsSinceEpoch(scheduledTime);

              return Card(
                child: ListTile(
                  title: Text(taskName),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Scheduled: ${DateFormat('yyyy-MM-dd HH:mm').format(taskDateTime)}'),
                      Text('Created: $timestamp'),
                      Text('Status: ${taskStatus == 'done' ? 'Completed' : 'Pending'}'),
                    ],
                  ),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        icon: Icon(Icons.notifications, color: Colors.blue),
                        onPressed: () => _sendReminderToPi(taskName, scheduledTime), // Send reminder to Raspberry Pi
                      ),
                      IconButton(
                        icon: Icon(Icons.check_box, color: taskStatus == 'done' ? Colors.green : Colors.grey),
                        onPressed: taskStatus == 'done'
                            ? null
                            : () => _markTaskAsDone(taskId), // Mark task as done
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}