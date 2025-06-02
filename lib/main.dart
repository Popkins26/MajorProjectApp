import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart'; // <-- Import dotenv
import 'package:major_project_app/firebase_options.dart';
import 'package:major_project_app/pages/first_page.dart';
import 'package:major_project_app/pages/login_page.dart';
import 'package:major_project_app/pages/register_page.dart';
import 'package:major_project_app/pages/planner_page.dart';
import 'package:major_project_app/pages/user_profile_edit.dart';
import 'package:major_project_app/pages/voice_notes.dart';
import 'package:major_project_app/pages/voice_recording_page.dart';
import 'package:major_project_app/pages/task_record_page.dart';
import 'package:major_project_app/pages/select_recording_page.dart';
import 'package:major_project_app/services/auth/auth_gate.dart';
import 'package:major_project_app/services/auth/auth_service.dart';
import 'package:provider/provider.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';
import 'package:webview_flutter_wkwebview/webview_flutter_wkwebview.dart';
import 'pages/drawer_page.dart';
import 'pages/video_feed_page.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Firebase
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

  // Initialize WebView with platform-specific implementation
  late final PlatformWebViewControllerCreationParams params;
  if (WebViewPlatform.instance is WebKitWebViewPlatform) {
    params = WebKitWebViewControllerCreationParams(
      allowsInlineMediaPlayback: true,
      mediaTypesRequiringUserAction: const <PlaybackMediaTypes>{},
    );
  } else {
    params = const PlatformWebViewControllerCreationParams();
  }

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
        '/login':
            (context) => LoginPage(
              onTap: () {
                Navigator.pushNamed(context, '/register');
              },
            ),
        '/register':
            (context) => RegisterPage(
              onTap: () {
                Navigator.pushNamed(context, '/login');
              },
            ),
        '/first': (context) => const FirstPage(),
        '/planner': (context) => const PlannerPage(),
        '/voiceRecording': (context) => VoiceRecorderPage(),
        '/taskRecord': (context) => TaskSchedulerPage(),
        '/selectRecording': (context) => SelectRecordingPage(),
        '/editProfile': (context) => UserProfileEditPage(),
        '/voiceNotes': (context) => VoiceNotesPage(),
      },
    );
  }
}

class MainScaffold extends StatelessWidget {
  const MainScaffold({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      drawer: const DrawerPage(),
      appBar: AppBar(title: const Text('Care Taker Bot')),
      body: const VideoFeedPage(),
    );
  }
}
