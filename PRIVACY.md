# Privacy Policy

**Smarty** ("we", "our", "the App") respects your privacy. This policy explains how information is processed by the desktop application.

## 1. Local Processing First
Smarty is designed with a **privacy-first local execution** philosophy. 
- **Webcam Feed**: Your webcam stream is processed entirely locally on your machine for Hand Gesture Tracking, Eye Tracking HUDs, and Face Registration. Raw video frames are never recorded, saved, or uploaded to any remote server.
- **Biometric Templates**: Your face registration templates are generated and verified locally using local machine learning libraries (MediaPipe Face Landmarker). The registration file (`reference.jpg`) is saved locally inside the application directory. No biometric database or cloud server holds this data.

## 2. Remote Services & Cloud APIs
To fulfill intelligence and voice features, the App communicates with the following external endpoints:
- **Google Gemini API**: Voice conversations and general intelligence queries are sent to Google's Gemini servers via your configured API key. This data is handled in accordance with Google's API Terms of Service.
- **Web Automation Agent**: Browser automation queries are performed via a local Chromium instance powered by Playwright. No external proxy servers are used unless configured manually.

## 3. Local Smart Devices (Kasa & Printers)
Smarty discovers and manages workspace appliances (TP-Link Kasa smart lamps, Moonraker/OctoPrint 3D printer controllers) directly over your Local Area Network (LAN). No local network credentials or telemetry are sent to remote services.

## 4. Updates & Modifications
Any updates to this privacy policy will be documented in the source code repository. You are encouraged to review local configuration files (`settings.json`) to control feature access.
