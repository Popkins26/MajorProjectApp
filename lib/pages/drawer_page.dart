import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:major_project_app/pages/pending_tasks_page.dart';
import 'package:major_project_app/pages/planner_page.dart'; // Import PlannerPage
import 'medical_history_page.dart';
import 'user_profile_page.dart';

class DrawerPage extends StatefulWidget {
  const DrawerPage({Key? key}) : super(key: key);

  @override
  _DrawerPageState createState() => _DrawerPageState();
}

class _DrawerPageState extends State<DrawerPage> {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;

  String _userName = "User Name";
  String _userEmail = "user@example.com";

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
              backgroundColor: const Color.fromRGBO(255, 255, 255, 1),
              child: Icon(Icons.person, size: 50, color: Colors.blue),
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
            title: Text("Planner"), // Add Planner option
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => PlannerPage()),
              );
            },
          ),
        ],
      ),
    );
  }
}