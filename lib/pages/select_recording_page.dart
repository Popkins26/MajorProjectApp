import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

class SelectRecordingPage extends StatelessWidget {
  const SelectRecordingPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Select Recording')),
      body: StreamBuilder(
        stream: FirebaseFirestore.instance.collection('recordings').snapshots(),
        builder: (context, AsyncSnapshot<QuerySnapshot> snapshot) {
          if (!snapshot.hasData) return Center(child: CircularProgressIndicator());

          final recordings = snapshot.data!.docs;

          if (recordings.isEmpty) {
            return Center(child: Text('No recordings available.'));
          }

          return ListView.builder(
            itemCount: recordings.length,
            itemBuilder: (context, index) {
              final recording = recordings[index];
              final data = recording.data() as Map<String, dynamic>;
              final recordingName = data['name'] ?? 'Unnamed Recording';
              final downloadUrl = data['downloadUrl'];

              return ListTile(
                title: Text(recordingName),
                trailing: Icon(Icons.check),
                onTap: () {
                  Navigator.pop(context, downloadUrl); // Return the selected recording's URL
                },
              );
            },
          );
        },
      ),
    );
  }
}