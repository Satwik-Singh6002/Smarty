# Smarty Scripts

This directory houses the core launch and maintenance utilities for the Smarty AI Assistant.

## Core Scripts

- `launch.js`: The central orchestrator that spawns the Python FastAPI backend, Vite dev server, and Electron desktop shell. Used by `npm run dev` and `npm start`.
- `register_face.py`: Interactive CLI tool for enrolling the owner's facial biometric landmarks (5-angle progressive sampling) with MediaPipe.
- `capture_face.py`: Quick helper tool to capture and preview a webcam snapshot.

## Subdirectories

- `debug/`: Developer testing and subsystem verification suite. See [`debug/README.md`](debug/README.md) for details.
