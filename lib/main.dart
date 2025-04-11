import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart'; // <-- Import dotenv
import 'package:major_project_app/firebase_options.dart';
import 'package:major_project_app/pages/first_page.dart';
import 'package:major_project_app/pages/login_page.dart';
import 'package:major_project_app/pages/register_page.dart';
import 'package:major_project_app/pages/planner_page.dart';
import 'package:major_project_app/pages/voice_recording_page.dart';
import 'package:major_project_app/pages/task_record_page.dart';
import 'package:major_project_app/pages/select_recording_page.dart';
import 'package:major_project_app/services/auth/auth_gate.dart';
import 'package:major_project_app/services/auth/auth_service.dart';
import 'package:provider/provider.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();


  

  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  runApp(
    ChangeNotifierProvider(
      create: (context) => AuthService(),
      child: const MyApp(),
    ),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      initialRoute: '/auth',
      routes: {
        '/auth': (context) => AuthGate(),
        '/login': (context) => LoginPage(
              onTap: () {
                Navigator.pushNamed(context, '/register');
              },
            ),
        '/register': (context) => RegisterPage(
              onTap: () {
                Navigator.pushNamed(context, '/login');
              },
            ),
        '/first': (context) => const FirstPage(),
        '/planner': (context) => const PlannerPage(),
        '/voiceRecording': (context) => VoiceRecorderPage(),
        '/taskRecord': (context) => TaskSchedulerPage(),
        '/selectRecording': (context) => SelectRecordingPage(),
      },
    );
  }
}
