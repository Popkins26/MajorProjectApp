import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;

class AuthService extends ChangeNotifier {
  // Firebase auth instance
  final FirebaseAuth _firebaseAuth = FirebaseAuth.instance;

  // Google Sign-In instance
  final GoogleSignIn _googleSignIn = GoogleSignIn(
    scopes: ['email', 'https://www.googleapis.com/auth/calendar'],
  );

  // Getter for GoogleSignIn
  GoogleSignIn get googleSignIn => _googleSignIn;

  // Sign in with email & password
  Future<UserCredential> signInWithEmailAndPassword(
    String email,
    String password,
  ) async {
    try {
      UserCredential userCredential = await _firebaseAuth
          .signInWithEmailAndPassword(email: email, password: password);

      return userCredential;
    } on FirebaseAuthException catch (e) {
      throw Exception(e.code);
    }
  }

  // Google Sign-In
  Future<UserCredential?> signInWithGoogle() async {
    try {
      final GoogleSignInAccount? googleUser = await _googleSignIn.signIn();
      if (googleUser == null) return null;

      final GoogleSignInAuthentication googleAuth =
          await googleUser.authentication;

      final AuthCredential credential = GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken: googleAuth.idToken,
      );

      final UserCredential userCredential =
          await _firebaseAuth.signInWithCredential(credential);

      // Send login data to Raspberry Pi
      await sendLoginDetailsToRaspberryPi();

      return userCredential;
    } catch (e) {
      print("Google Sign-In failed: $e");
      return null;
    }
  }

  // Sign out user from Firebase and Google
  Future<void> signOut() async {
    await _firebaseAuth.signOut();
    await _googleSignIn.signOut(); // Also sign out from Google
  }

  // Send login details to Raspberry Pi
  Future<void> sendLoginDetailsToRaspberryPi() async {
    final user = _firebaseAuth.currentUser;
    if (user == null) return;

    final idToken = await user.getIdToken();
    final name = user.displayName ?? "";
    final email = user.email ?? "";
    final photoUrl = user.photoURL ?? "";

    final uri = Uri.parse('http://<PI_LOCAL_IP>:5000/token'); // Replace with actual IP

    try {
      final response = await http.post(uri, body: {
        'token': idToken,
        'name': name,
        'email': email,
        'photo_url': photoUrl,
      });

      if (response.statusCode == 200) {
        print("✅ Successfully sent login to Raspberry Pi.");
      } else {
        print("❌ Failed to send login to Raspberry Pi: ${response.statusCode}");
      }
    } catch (e) {
      print("🚫 Error sending login to Pi: $e");
    }
  }
}
