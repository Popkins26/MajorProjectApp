import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:major_project_app/pages/pending_tasks_page.dart';
import 'package:major_project_app/pages/planner_page.dart'; // Import PlannerPage
import 'package:major_project_app/pages/voice_notes.dart'; // Import VoiceNotesPage
import 'medical_history_page.dart';
import 'user_profile_page.dart';
import 'emergency_page.dart'; // Import EmergencyPage

class DrawerPage extends StatefulWidget {
  const DrawerPage({super.key});

  @override
  _DrawerPageState createState() => _DrawerPageState();
}

class _DrawerPageState extends State<DrawerPage> {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;

  String _userName = "User Name";
  String _userEmail = "user@example.com";
  String? _profileImageUrl;

  @override
  void initState() {
    super.initState();
    _loadUserData();
  }

  Future<void> _loadUserData() async {
    final user = _auth.currentUser;
    if (user != null) {
      setState(() {
        _userEmail = user.email ?? "user@example.com";
      });

      final doc = await _firestore.collection('users').doc(user.uid).get();
      if (doc.exists) {
        final data = doc.data();
        setState(() {
          _userName = data?['name'] ?? "User Name";
          _profileImageUrl = data?['profileImageUrl'];
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Drawer(
      child: Column(
        children: [
          UserAccountsDrawerHeader(
            accountName: Text(_userName),
            accountEmail: Text(_userEmail),
            currentAccountPicture: CircleAvatar(
              backgroundImage:
                  _profileImageUrl != null
                      ? NetworkImage(_profileImageUrl!)
                      : AssetImage('assets/default_avatar.png')
                          as ImageProvider,
              backgroundColor: Colors.grey[200],
            ),
          ),
          ListTile(
            leading: Icon(Icons.person),
            title: Text("User Profile"),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => UserProfilePage()),
              );
            },
          ),
          ListTile(
            leading: Icon(Icons.history),
            title: Text("Medical History"),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => MedicalHistoryPage()),
              );
            },
          ),
          ListTile(
            leading: Icon(Icons.task),
            title: Text("Pending Tasks"),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => PendingTasksPage()),
              );
            },
          ),
          ListTile(
            leading: Icon(Icons.calendar_today),
            title: Text("Planner"),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => PlannerPage()),
              );
            },
          ),
          ListTile(
            leading: Icon(Icons.mic),
            title: Text("Voice Notes"),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => VoiceNotesPage()),
              );
            },
          ),
          ListTile(
            leading: Icon(Icons.warning, color: Colors.red),
            title: Text("Emergency", style: TextStyle(color: Colors.red)),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => EmergencyPage()),
              );
            },
          ),
          Spacer(), // Logout button bottom
          ListTile(
            leading: Icon(Icons.logout),
            title: Text("Logout"),
            onTap: () async {
              await _auth.signOut();
              Navigator.pushReplacementNamed(context, '/login');
            },
          ),
        ],
      ),
    );
  }
}
