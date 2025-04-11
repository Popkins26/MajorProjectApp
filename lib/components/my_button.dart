import 'package:flutter/material.dart';

class MyButton extends StatelessWidget {
  final VoidCallback onTap;
  final String text;

  const MyButton({
    super.key,
    required this.onTap,
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: EdgeInsets.symmetric(vertical: 15, horizontal: 20),
        decoration: BoxDecoration(
          color: Colors.black,
          borderRadius: BorderRadius.circular(10),
        ), // BoxDecoration
        child: Center(
          child: Text(
            text,
            style: TextStyle(
              color: Colors.white, // Make text visible
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
          ),
        ), // Center
      ), // Container
    ); // GestureDetector
  }
}
