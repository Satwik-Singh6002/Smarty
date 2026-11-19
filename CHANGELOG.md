# Changelog

All notable changes to **Smarty** will be documented in this file.

## [1.0.0] - 2026-06-07

### Added
- **Secure Preload Bridge**: Replaced direct Node.js access in Electron renderer process with secure IPC context bridge (`preload.js`), closing major security vulnerability.
- **Biometric Security**: Added face biometric registration utility and local authentication check upon boot.
- **Premium User Interface**: Modern CSS customization with Inter and JetBrains Mono fonts, glowing visual status, glassmorphic floating panels, and smooth layout resizing.
- **Holographic Gesture Controls**: Hand tracking controls using MediaPipe for Minority Report-style window dragging, resizing, and click simulation.
- **Parametric CAD Agent**: Real-time voice-to-3D CAD modeling with Three.js rendering and local design iteration.
- **OrcaSlicer Integration**: Automatic slicing and wireless upload pipeline for printer controllers (OctoPrint & Moonraker).
- **Smart Workspace (Kasa)**: Automated smart home lamp power, brightness, and color temperature controls based on context or assistant chat triggers.
- **Keyboard Shortcuts**: Added `Ctrl+M` to mute/unmute microphone and `Escape` to close modular interface windows and deny authorization requests.
- **Error Boundaries**: Wrapped main application in a React Error Boundary screen to handle runtime crashes gracefully and allow soft resets.
- **Packaging Scripts**: Configured `electron-builder` with custom icon and NSIS installer scripts for commercial distribution.

### Fixed
- **Memory Growth Bug**: Fixed server.py memory writing error where chat history was missing file writes.
- **Duplicate Imports**: Removed duplicate package loads in backend `server.py` to optimize import speeds.
- **System Instructions**: Removed personal references from voice loop guidelines, ensuring a clean white-label product experience.
- **Connection States**: Added reactive connection status overlays with descriptive websocket events.
