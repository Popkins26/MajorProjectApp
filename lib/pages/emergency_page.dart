import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

class EmergencyPage extends StatefulWidget {
  const EmergencyPage({super.key});

  @override
  _EmergencyPageState createState() => _EmergencyPageState();
}

class _EmergencyPageState extends State<EmergencyPage> {
  String? serverUrl;
  bool isStreaming = false;
  bool isLoading = false;
  String? errorMsg;
  late WebViewController _webViewController;

  @override
  void initState() {
    super.initState();
    _webViewController =
        WebViewController()
          ..setJavaScriptMode(JavaScriptMode.unrestricted)
          ..setBackgroundColor(Colors.black)
          ..setNavigationDelegate(
            NavigationDelegate(
              onPageFinished: (String url) {
                setState(() {
                  isLoading = false;
                });
              },
              onWebResourceError: (WebResourceError error) {
                setState(() {
                  errorMsg = 'Error loading stream: ${error.description}';
                  isLoading = false;
                });
              },
            ),
          );
    fetchStreamUrl();
  }

  Future<void> fetchStreamUrl() async {
    final doc =
        await FirebaseFirestore.instance
            .collection('camera')
            .doc('stream')
            .get();
    if (doc.exists && doc.data() != null && doc['url'] != null) {
      setState(() {
        serverUrl = doc['url'];
      });
    }
  }

  Future<void> startStream() async {
    if (serverUrl == null) {
      setState(() {
        errorMsg = 'No stream URL found. Please refresh.';
      });
      return;
    }
    setState(() {
      isLoading = true;
      errorMsg = null;
    });

    try {
      // First, ensure the stream is started on the server
      final startResponse = await http.post(
        Uri.parse('$serverUrl/start-stream'),
      );
      if (startResponse.statusCode == 200) {
        final data = json.decode(startResponse.body);
        if (data['status'] == 'success') {
          setState(() {
            isStreaming = true;
          });
          // Load the stream URL in the WebView
          await _webViewController.loadRequest(Uri.parse('$serverUrl/stream'));
        } else {
          setState(() {
            errorMsg = data['message'];
          });
        }
      } else {
        setState(() {
          errorMsg = 'Failed to start stream: ${startResponse.body}';
        });
      }
    } catch (e) {
      setState(() {
        errorMsg = 'Error: ${e.toString()}';
      });
    } finally {
      setState(() {
        isLoading = false;
      });
    }
  }

  Future<void> stopStream() async {
    if (serverUrl == null) return;
    try {
      final response = await http.post(Uri.parse('$serverUrl/stop-stream'));
      if (response.statusCode == 200) {
        setState(() {
          isStreaming = false;
        });
        // Clear the WebView
        await _webViewController.loadRequest(Uri.parse('about:blank'));
      }
    } catch (e) {
      setState(() {
        errorMsg = 'Error stopping stream: ${e.toString()}';
      });
    }
  }

  Widget _buildStreamView() {
    if (isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (errorMsg != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(errorMsg!, style: const TextStyle(color: Colors.red)),
            const SizedBox(height: 16),
            ElevatedButton(onPressed: startStream, child: const Text('Retry')),
          ],
        ),
      );
    }
    if (isStreaming) {
      return WebViewWidget(controller: _webViewController);
    }
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text('Press "View Stream" to start the camera feed.'),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Flexible(
                child: Text(
                  serverUrl != null
                      ? 'Stream URL: ${serverUrl!}'
                      : 'No stream URL found.',
                  style: const TextStyle(fontSize: 12, color: Colors.grey),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              IconButton(
                icon: const Icon(Icons.refresh),
                tooltip: 'Refresh stream URL',
                onPressed: fetchStreamUrl,
              ),
            ],
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Emergency',
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
      body: Container(
        color: const Color(0xFFF5F5F5),
        child: Column(
          children: [
            Expanded(child: _buildStreamView()),
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: ElevatedButton.icon(
                onPressed:
                    isLoading || serverUrl == null
                        ? null
                        : (isStreaming ? stopStream : startStream),
                icon: Icon(isStreaming ? Icons.stop : Icons.camera),
                label: Text(isStreaming ? 'Stop Stream' : 'View Stream'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: isStreaming ? Colors.red : Colors.green,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  textStyle: const TextStyle(fontSize: 18),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
