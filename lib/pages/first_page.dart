import 'package:flutter/material.dart';
import 'package:major_project_app/pages/task_record_page.dart';
import 'package:major_project_app/pages/voice_recording_page.dart';
import 'package:major_project_app/pages/video_feed_page.dart'; // Import VideoFeedPage
import 'package:major_project_app/services/auth/auth_service.dart';
import 'package:provider/provider.dart';
import 'drawer_page.dart';

class FirstPage extends StatefulWidget {
  const FirstPage({super.key});

  @override
  _FirstPageState createState() => _FirstPageState();
}

class _FirstPageState extends State<FirstPage> {
  int _selectedIndex = 0;

  void _onItemTapped(int index) {
    setState(() {
      _selectedIndex = index;
    });
  }

  void _logout() async {
    final authService = Provider.of<AuthService>(context, listen: false);
    await authService.signOut();
    Navigator.pushReplacementNamed(context, '/login');
  }

  @override
  Widget build(BuildContext context) {
    final List<Widget> pages = [
      VoiceRecorderPage(),
      TaskSchedulerPage(),
      VideoFeedPage(), // Use VideoFeedPage for live video feed
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Center(
          child: Text(
            "Care Taker Bot",
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
        ),
        backgroundColor: Colors.white,
        elevation: 0.5,
        iconTheme: const IconThemeData(color: Colors.black87),
        titleTextStyle: const TextStyle(
          color: Colors.black87,
          fontWeight: FontWeight.bold,
          fontSize: 20,
        ),
        actions: [
          IconButton(icon: const Icon(Icons.logout), onPressed: _logout),
        ],
      ),
      drawer: const DrawerPage(), // PlannerPage moved to the drawer
      body: Container(
        color: const Color(0xFFF5F5F5),
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 500),
          child: pages[_selectedIndex],
        ),
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: _onItemTapped,
        selectedItemColor: Colors.blue,
        unselectedItemColor: Colors.grey,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.mic),
            label: 'Voice Recording',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.assignment),
            label: 'Task Scheduling',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.videocam),
            label: 'Video Feed',
          ),
        ],
      ),
    );
  }
}
