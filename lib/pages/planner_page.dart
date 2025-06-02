import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:googleapis/calendar/v3.dart' as calendar;
import 'package:googleapis_auth/googleapis_auth.dart' as auth;
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;
import 'package:firebase_auth/firebase_auth.dart';

class PlannerPage extends StatefulWidget {
  const PlannerPage({super.key});

  @override
  _PlannerPageState createState() => _PlannerPageState();
}

class _PlannerPageState extends State<PlannerPage> {
  List<Map<String, dynamic>> dailyTasks = [];
  List<Map<String, dynamic>> doctorAppointments = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) return;

    DocumentSnapshot snapshot =
        await FirebaseFirestore.instance
            .collection('users')
            .doc(user.uid)
            .get();
    if (snapshot.exists) {
      setState(() {
        dailyTasks = List<Map<String, dynamic>>.from(
          snapshot['dailyTasks'] ?? [],
        );
        doctorAppointments = List<Map<String, dynamic>>.from(
          snapshot['doctorAppointments'] ?? [],
        );
      });
    }
  }

  Future<void> _saveData() async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) return;

    await FirebaseFirestore.instance.collection('users').doc(user.uid).set({
      'dailyTasks': dailyTasks,
      'doctorAppointments': doctorAppointments,
    });
  }

  Future<Map<String, dynamic>?> _addToGoogleCalendar(
    String title,
    DateTime dateTime,
  ) async {
    try {
      final GoogleSignIn googleSignIn = GoogleSignIn(
        scopes: ['email', calendar.CalendarApi.calendarScope],
      );

      final GoogleSignInAccount? googleUser =
          await googleSignIn.signInSilently() ?? await googleSignIn.signIn();

      final googleAuth = await googleUser?.authentication;

      if (googleUser == null ||
          googleAuth == null ||
          googleAuth.accessToken == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Google access token not available.")),
        );
        return null;
      }

      final authClient = auth.authenticatedClient(
        http.Client(),
        auth.AccessCredentials(
          auth.AccessToken(
            'Bearer',
            googleAuth.accessToken!,
            DateTime.now().toUtc().add(const Duration(hours: 1)),
          ),
          null,
          [calendar.CalendarApi.calendarScope],
        ),
      );

      final calendarApi = calendar.CalendarApi(authClient);
      final event =
          calendar.Event()
            ..summary = title
            ..start =
                (calendar.EventDateTime()
                  ..dateTime = dateTime.toUtc()
                  ..timeZone = "UTC")
            ..end =
                (calendar.EventDateTime()
                  ..dateTime = dateTime.add(const Duration(hours: 1)).toUtc()
                  ..timeZone = "UTC");

      final createdEvent = await calendarApi.events.insert(event, "primary");

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Appointment added to Google Calendar!")),
      );

      return {'calendarEventId': createdEvent.id};
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error adding to Google Calendar: $e")),
      );
      return null;
    }
  }

  Future<void> _deleteGoogleCalendarEvent(String? eventId) async {
    if (eventId == null) return;
    try {
      final GoogleSignIn googleSignIn = GoogleSignIn(
        scopes: [calendar.CalendarApi.calendarScope],
      );

      final GoogleSignInAccount? googleUser =
          await googleSignIn.signInSilently() ?? await googleSignIn.signIn();
      final googleAuth = await googleUser?.authentication;

      if (googleUser == null ||
          googleAuth == null ||
          googleAuth.accessToken == null)
        return;

      final authClient = auth.authenticatedClient(
        http.Client(),
        auth.AccessCredentials(
          auth.AccessToken(
            'Bearer',
            googleAuth.accessToken!,
            DateTime.now().toUtc().add(const Duration(hours: 1)),
          ),
          null,
          [calendar.CalendarApi.calendarScope],
        ),
      );

      final calendarApi = calendar.CalendarApi(authClient);
      await calendarApi.events.delete("primary", eventId);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error deleting from Google Calendar: $e")),
      );
    }
  }

  void _addDailyTask() {
    _showTaskDialog(isDoctorAppointment: false);
  }

  void _addDoctorAppointment() {
    _showTaskDialog(isDoctorAppointment: true);
  }

  void _deleteTask(int index, bool isDoctorAppointment) async {
    if (isDoctorAppointment) {
      final eventId = doctorAppointments[index]['calendarEventId'];
      await _deleteGoogleCalendarEvent(eventId);
      setState(() {
        doctorAppointments.removeAt(index);
      });
    } else {
      setState(() {
        dailyTasks.removeAt(index);
      });
    }
    _saveData();
  }

  void _showTaskDialog({required bool isDoctorAppointment}) {
    TextEditingController taskController = TextEditingController();
    DateTime? selectedDateTime;

    showDialog(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: Text(
                isDoctorAppointment
                    ? "Add Doctor Appointment"
                    : "Add Daily Task",
              ),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: taskController,
                    decoration: const InputDecoration(
                      hintText: "Enter details",
                    ),
                  ),
                  const SizedBox(height: 10),
                  ElevatedButton(
                    onPressed: () async {
                      final pickedDate = await showDatePicker(
                        context: context,
                        initialDate: DateTime.now(),
                        firstDate: DateTime.now(),
                        lastDate: DateTime(2100),
                      );

                      if (pickedDate != null) {
                        final pickedTime = await showTimePicker(
                          context: context,
                          initialTime: TimeOfDay.now(),
                        );

                        if (pickedTime != null) {
                          final dateTime = DateTime(
                            pickedDate.year,
                            pickedDate.month,
                            pickedDate.day,
                            pickedTime.hour,
                            pickedTime.minute,
                          );

                          setDialogState(() {
                            selectedDateTime = dateTime;
                          });
                        }
                      }
                    },
                    child: Text(
                      selectedDateTime == null
                          ? "Select Date & Time"
                          : DateFormat(
                            'yyyy-MM-dd – HH:mm',
                          ).format(selectedDateTime!),
                    ),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text("Cancel"),
                ),
                ElevatedButton(
                  onPressed: () async {
                    if (taskController.text.isNotEmpty &&
                        selectedDateTime != null) {
                      final task = {
                        'task': taskController.text,
                        'time': selectedDateTime.toString(),
                      };

                      if (isDoctorAppointment) {
                        final calendarInfo = await _addToGoogleCalendar(
                          taskController.text,
                          selectedDateTime!,
                        );
                        if (calendarInfo != null) {
                          task['calendarEventId'] =
                              calendarInfo['calendarEventId'];
                        }
                        setState(() {
                          doctorAppointments.add(task);
                        });
                      } else {
                        setState(() {
                          dailyTasks.add(task);
                        });
                      }

                      _saveData();
                      Navigator.pop(context);
                    }
                  },
                  child: const Text("Add"),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Planner',
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
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Expanded(
                  flex: 6,
                  child: _buildPlannerCard(
                    title: "Daily Tasks",
                    items: dailyTasks,
                    onAdd: _addDailyTask,
                    isDoctorAppointment: false,
                  ),
                ),
                const SizedBox(height: 10),
                Expanded(
                  flex: 4,
                  child: _buildPlannerCard(
                    title: "Upcoming Doctor Appointments",
                    items: doctorAppointments,
                    onAdd: _addDoctorAppointment,
                    isDoctorAppointment: true,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildPlannerCard({
    required String title,
    required List<Map<String, dynamic>> items,
    required VoidCallback onAdd,
    required bool isDoctorAppointment,
  }) {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 18,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(
                    Icons.add_circle,
                    size: 32,
                    color: Colors.blue,
                  ),
                  onPressed: onAdd,
                ),
              ],
            ),
            const Divider(thickness: 1.5),
            Expanded(
              child:
                  items.isEmpty
                      ? const Center(child: Text("No tasks added."))
                      : ListView.builder(
                        itemCount: items.length,
                        itemBuilder: (context, index) {
                          return ListTile(
                            title: Text(items[index]['task']),
                            subtitle: Text(
                              DateFormat(
                                'EEEE, MMM d – hh:mm a',
                              ).format(DateTime.parse(items[index]['time'])),
                            ),
                            trailing: IconButton(
                              icon: const Icon(Icons.delete, color: Colors.red),
                              onPressed:
                                  () => _deleteTask(index, isDoctorAppointment),
                            ),
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
