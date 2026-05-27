import React, { useEffect, useState, useRef } from 'react';
import io from 'socket.io-client';

import Visualizer from './components/Visualizer';
import TopAudioBar from './components/TopAudioBar';
import CadWindow from './components/CadWindow';
import BrowserWindow from './components/BrowserWindow';
import ChatModule from './components/ChatModule';
import ToolsModule from './components/ToolsModule';
import { Mic, MicOff, Settings, X, Minus, Power, Video, VideoOff, Layout, Hand, Printer, Clock } from 'lucide-react';
import { FilesetResolver, HandLandmarker, FaceLandmarker } from '@mediapipe/tasks-vision';
// MemoryPrompt removed - memory is now actively saved to project
import ConfirmationPopup from './components/ConfirmationPopup';
import AuthLock from './components/AuthLock';

import KasaWindow from './components/KasaWindow';
import PrinterWindow from './components/PrinterWindow';
import SettingsWindow from './components/SettingsWindow';



const socket = io('http://127.0.0.1:8000', { transports: ['websocket'] });
const { ipcRenderer } = window.require('electron');

// Global variables to prevent duplicate HandLandmarker and FaceLandmarker initialization in React.StrictMode
let globalHandLandmarker = null;
let globalFaceLandmarker = null;
let globalHandLandmarkerPromise = null;
let globalTfScriptPromise = null;
let globalCocoModelPromise = null;

function App() {
    const [status, setStatus] = useState('Disconnected');
    const [socketConnected, setSocketConnected] = useState(socket.connected); // Track socket connection reactively
    // Auth State
    const [isAuthenticated, setIsAuthenticated] = useState(false);

    // Initialize from LocalStorage to prevent flash of UI
    const [isLockScreenVisible, setIsLockScreenVisible] = useState(false);

    // Local state for tracking settings, also init from local storage
    const [faceAuthEnabled, setFaceAuthEnabled] = useState(() => {
        return localStorage.getItem('face_auth_enabled') === 'true';
    });
    const [isFaceRegistered, setIsFaceRegistered] = useState(false);


    const [isConnected, setIsConnected] = useState(true); // Power state DEFAULT ON
    const [isMuted, setIsMuted] = useState(false); // Mic state DEFAULT UNMUTED
    const [isVideoOn, setIsVideoOn] = useState(false); // Video state
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [cadData, setCadData] = useState(null);
    const [cadThoughts, setCadThoughts] = useState(''); // Streaming AI thoughts
    const [cadRetryInfo, setCadRetryInfo] = useState({ attempt: 1, maxAttempts: 3, error: null }); // Retry status
    const [browserData, setBrowserData] = useState({ image: null, logs: [] });
    // showMemoryPrompt removed - memory is now actively saved to project
    const [confirmationRequest, setConfirmationRequest] = useState(null); // { id, tool, args }
    const [kasaDevices, setKasaDevices] = useState([]);
    const [showKasaWindow, setShowKasaWindow] = useState(false);
    const [showPrinterWindow, setShowPrinterWindow] = useState(false);
    const [showCadWindow, setShowCadWindow] = useState(false);
    const [showBrowserWindow, setShowBrowserWindow] = useState(false);

    // Printing workflow status (for top toolbar display)
    const [slicingStatus, setSlicingStatus] = useState({ active: false, percent: 0, message: '' });
    const [activePrintStatus, setActivePrintStatus] = useState(null); // {printer, progress_percent, time_elapsed, state}
    const [printerCount, setPrinterCount] = useState(0); // Count of connected printers
    const [currentTime, setCurrentTime] = useState(new Date()); // Live clock
    const [overloadActive, setOverloadActive] = useState(false);


    // RESTORED STATE
    const [aiAudioData, setAiAudioData] = useState(new Array(64).fill(0));
    const [micAudioData, setMicAudioData] = useState(new Array(32).fill(0));
    const [fps, setFps] = useState(0);

    // Device states - microphones, speakers, webcams
    const [micDevices, setMicDevices] = useState([]);
    const [speakerDevices, setSpeakerDevices] = useState([]);
    const [webcamDevices, setWebcamDevices] = useState([]);

    // Selected device IDs - restored from localStorage
    const [selectedMicId, setSelectedMicId] = useState(() => localStorage.getItem('selectedMicId') || '');
    const [selectedSpeakerId, setSelectedSpeakerId] = useState(() => localStorage.getItem('selectedSpeakerId') || '');
    const [selectedWebcamId, setSelectedWebcamId] = useState(() => localStorage.getItem('selectedWebcamId') || '');
    const [showSettings, setShowSettings] = useState(false);
    const [currentProject, setCurrentProject] = useState('default');

    // Modular Mode State
    const [isModularMode, setIsModularMode] = useState(false);
    const [elementPositions, setElementPositions] = useState({
        video: { x: 40, y: 80 }, // Initial positions (approximate)
        visualizer: { x: window.innerWidth / 2, y: window.innerHeight / 2 - 150 },
        chat: { x: window.innerWidth / 2, y: window.innerHeight / 2 + 100 },
        cad: { x: window.innerWidth / 2 + 300, y: window.innerHeight / 2 },
        browser: { x: window.innerWidth / 2 - 300, y: window.innerHeight / 2 },
        kasa: { x: window.innerWidth / 2 + 350, y: window.innerHeight / 2 - 100 },
        printer: { x: window.innerWidth / 2 - 350, y: window.innerHeight / 2 - 100 },
        tools: { x: window.innerWidth / 2, y: window.innerHeight - 100 } // Fixed bottom OFFSET
    });

    const [elementSizes, setElementSizes] = useState({
        visualizer: { w: 550, h: 350 },
        chat: { w: 550, h: 220 },
        tools: { w: 500, h: 80 }, // Approx
        cad: { w: 400, h: 400 },
        browser: { w: 550, h: 380 },
        video: { w: 320, h: 180 },
        kasa: { w: 300, h: 380 }, // Approx
        printer: { w: 380, h: 380 } // Approx
    });
    const [activeDragElement, setActiveDragElement] = useState(null);

    // Z-Index Stacking Order (last element = highest z-index)
    const [zIndexOrder, setZIndexOrder] = useState([
        'visualizer', 'chat', 'tools', 'video', 'cad', 'browser', 'kasa', 'printer'
    ]);

    // TensorFlow and COCO-SSD state
    const [tfLoaded, setTfLoaded] = useState(false);
    const [cocoModel, setCocoModel] = useState(null);
    const latestPredictionsRef = useRef([]);

    // Hand Control State
    const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
    const [isPinching, setIsPinching] = useState(false);
    const [isHandTrackingEnabled, setIsHandTrackingEnabled] = useState(false); // DEFAULT OFF
    const [cursorSensitivity, setCursorSensitivity] = useState(2.0);

    // Refs for Loop Access (Avoiding Closure Staleness)
    const isHandTrackingEnabledRef = useRef(false); // DEFAULT OFF
    const cursorSensitivityRef = useRef(2.0);
    const handLandmarkerRef = useRef(null);
    const cursorTrailRef = useRef([]); // Stores last N positions for trail
    const [ripples, setRipples] = useState([]); // Visual ripples on click

    // Web Audio Context for Mic Visualization
    const audioContextRef = useRef(null);
    const analyserRef = useRef(null);
    const sourceRef = useRef(null);
    const animationFrameRef = useRef(null);

    // Video Refs
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const transmissionCanvasRef = useRef(null); // Dedicated canvas for resizing payload
    const videoIntervalRef = useRef(null);
    const lastFrameTimeRef = useRef(0);
    const frameCountRef = useRef(0);
    const lastVideoTimeRef = useRef(-1);
    const lastFaceVideoTimeRef = useRef(-1);
    const faceLandmarkerRef = useRef(null);
    const latestHandLandmarksRef = useRef(null);
    const latestFaceLandmarksRef = useRef(null);

    // Ref to track video state for the loop (avoids closure staleness)
    const isVideoOnRef = useRef(false);
    const isModularModeRef = useRef(false);
    const elementPositionsRef = useRef(elementPositions);
    const activeDragElementRef = useRef(null);
    const lastActiveDragElementRef = useRef(null);
    const lastCursorPosRef = useRef({ x: 0, y: 0 });
    const lastWristPosRef = useRef({ x: 0, y: 0 }); // For stable fist gesture tracking

    // Smoothing and Snapping Refs
    const smoothedCursorPosRef = useRef({ x: 0, y: 0 });
    const snapStateRef = useRef({ isSnapped: false, element: null, snapPos: { x: 0, y: 0 } });

    // Mouse Drag Refs
    const dragOffsetRef = useRef({ x: 0, y: 0 });
    const isDraggingRef = useRef(false);

    // Update refs when state changes
    useEffect(() => {
        isModularModeRef.current = isModularMode;
        elementPositionsRef.current = elementPositions;
        isHandTrackingEnabledRef.current = isHandTrackingEnabled;
        cursorSensitivityRef.current = cursorSensitivity;
    }, [isModularMode, elementPositions, isHandTrackingEnabled, cursorSensitivity]);

    // Load TensorFlow JS and COCO-SSD dynamically (DISABLED for performance and to prevent WebGL Context Loss)
    useEffect(() => {
        // Disabled to optimize startup performance and prevent GPU thread blocking / WebGL context crashes.
        console.log("[TFJS Loader] COCO-SSD object detection is disabled for visual performance optimization.");
    }, []);

    // Live Clock Update
    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentTime(new Date());
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    // Centering Logic (Startup & Resize)
    useEffect(() => {
        const centerElements = () => {
            const width = window.innerWidth;
            const height = window.innerHeight;

            // Calculate available vertical space
            // Tools is fixed at bottom ~100px space
            const toolsY = height - 100;
            // ToolsModule uses translate(-50%, -50%). So its Center Y.
            // Let's reserve bottom 140px for tools to be safe and float it nicely.
            const toolsCenterY = height - 100;

            const gap = 20;

            // Chat: Anchor is Top-Center (translate(-50%, 0)).
            // We want Chat Bottom to be above Tools Top.
            // Tools Top = toolsCenterY - (ToolsHeight/2) approx 40 = height - 140;
            const chatBottomLimit = height - 140;

            // Dynamic Height Calculation to fit screen
            // Standard Heights
            let vizH = 400;
            let chatH = 250;
            const topBarHeight = 60;

            // Total needed: TopBar + Viz + Gap + Chat + Gap + Tools (140 reserved)
            const totalNeeded = topBarHeight + vizH + gap + chatH + gap + 140;

            if (height < totalNeeded) {
                // Scale down
                const available = height - topBarHeight - 140 - (gap * 2);
                // Allocate 60% to Viz, 40% to Chat
                vizH = available * 0.6;
                chatH = available * 0.4;
            }

            // Positions
            // Visualizer (Center Anchored)
            // Top of Viz = TopBarHeight. Center = TopBarHeight + VizH/2
            const vizY = topBarHeight + (vizH / 2); // Removed buffer

            // Chat (Top Anchored)
            // Top of Chat = TopBarHeight + VizH + Gap
            const chatY = topBarHeight + vizH + gap;

            setElementSizes(prev => ({
                ...prev,
                visualizer: { w: Math.min(600, width * 0.8), h: vizH },
                chat: { w: Math.min(600, width * 0.9), h: chatH }
            }));

            setElementPositions(prev => ({
                ...prev,
                visualizer: {
                    x: width / 2,
                    y: vizY
                },
                chat: {
                    x: width / 2,
                    y: chatY
                },
                tools: {
                    x: width / 2,
                    y: toolsCenterY
                }
            }));
        };

        // Center on mount
        centerElements();

        // Center on resize
        window.addEventListener('resize', centerElements);
        return () => window.removeEventListener('resize', centerElements);
    }, []);

    // Utility: Clamp position to viewport so component stays fully visible
    const clampToViewport = (pos, size) => {
        const margin = 10;
        const topBarHeight = 60;
        const width = window.innerWidth;
        const height = window.innerHeight;

        return {
            x: Math.max(size.w / 2 + margin, Math.min(width - size.w / 2 - margin, pos.x)),
            y: Math.max(size.h / 2 + margin + topBarHeight, Math.min(height - size.h / 2 - margin, pos.y))
        };
    };

    // Utility: Get z-index for an element based on stacking order
    const getZIndex = (id) => {
        const baseZ = 30; // Above background elements
        const index = zIndexOrder.indexOf(id);
        return baseZ + (index >= 0 ? index : 0);
    };

    // Utility: Bring element to front (highest z-index)
    const bringToFront = (id) => {
        setZIndexOrder(prev => {
            const filtered = prev.filter(el => el !== id);
            return [...filtered, id]; // Move to end = highest z-index
        });
    };

    // Ref to track if model has been auto-connected (prevents duplicate connections)
    const hasAutoConnectedRef = useRef(false);

    // Auto-Connect Model on Start (Only after Auth)
    useEffect(() => {
        // Only auto-connect once: when socket connected, authenticated
        if (isConnected && isAuthenticated && socketConnected && !hasAutoConnectedRef.current) {
            console.log("Auto-connecting to Text Chat...");
            hasAutoConnectedRef.current = true;

            // Trigger Kasa and Printer Discovery
            socket.emit('discover_kasa');
            socket.emit('discover_printers');

            // Connect to model with small delay for socket stability
            const timer = setTimeout(() => {
                const index = micDevices.findIndex(d => d.deviceId === selectedMicId);
                const queryDevice = micDevices.find(d => d.deviceId === selectedMicId);
                const deviceName = queryDevice ? queryDevice.label : null;
                console.log("Auto-connecting to model with device:", deviceName, "Index:", index);

                setStatus('Connecting...');
                socket.emit('start_text_chat', { muted: isMuted, device_index: index !== -1 ? index : null });
            }, 500);
        }
    }, [isConnected, isAuthenticated, socketConnected, micDevices, selectedMicId]);

    useEffect(() => {
        // Socket IO Setup
        socket.on('connect', () => {
            setStatus('Connected');
            setSocketConnected(true);
            socket.emit('get_settings');
        });
        socket.on('disconnect', () => {
            setStatus('Disconnected');
            setSocketConnected(false);
        });
        socket.on('status', (data) => {
            addMessage('System', data.msg);
            // Update status bar based on backend messages
            if (data.msg === 'A.D.A Started') {
                setStatus('Model Connected');
            } else if (data.msg === 'A.D.A Stopped') {
                setStatus('Connected');
            }
        });
        socket.on('overload_state', (data) => {
            console.log("Overload state event received:", data);
            setOverloadActive(data.active);
            if (data.active) {
                addMessage('System', '⚠️ WARNING: CORE OVERLOAD PROTOCOL ACTIVATED!');
            } else {
                addMessage('System', 'Core stabilization complete. Systems nominal.');
            }
        });
        socket.on('audio_data', (data) => {
            setAiAudioData(data.data);
        });
        socket.on('auth_status', (data) => {
            console.log("Auth Status:", data);
            setIsAuthenticated(data.authenticated);
            if (data.authenticated) {
                // Authenticated - hide lock screen after animation
                // Don't immediately hide - let AuthLock handle its animation
            } else {
                // Not authenticated - show lock screen
                setIsLockScreenVisible(true);
            }
        });

        socket.on('settings', (settings) => {
            console.log("[Settings] Received:", settings);
            if (settings && typeof settings.face_auth_enabled !== 'undefined') {
                setFaceAuthEnabled(settings.face_auth_enabled);
                localStorage.setItem('face_auth_enabled', settings.face_auth_enabled);
            }
            if (settings && typeof settings.is_face_registered !== 'undefined') {
                setIsFaceRegistered(settings.is_face_registered);
            }
        });
        socket.on('error', (data) => {
            console.error("Socket Error:", data);
            addMessage('System', `Error: ${data.msg}`);
        });
        socket.on('cad_data', (data) => {
            console.log("Received CAD Data:", data);
            setCadData(data);
            setCadThoughts(''); // Clear thoughts when generation complete
            setShowCadWindow(true); // Open window when data arrives
            // Auto-show the window if it's hidden, clamped to viewport
            if (!elementPositions.cad) {
                const size = { w: 400, h: 400 };
                const clamped = clampToViewport({ x: window.innerWidth / 2 + 150, y: window.innerHeight / 2 }, size);
                setElementPositions(prev => ({
                    ...prev,
                    cad: clamped
                }));
            }
        });
        socket.on('cad_status', (data) => {
            console.log("Received CAD Status:", data);
            // Extract retry info from extended payload
            if (data.attempt) {
                setCadRetryInfo({
                    attempt: data.attempt,
                    maxAttempts: data.max_attempts || 3,
                    error: data.error
                });
            }
            if (data.status === 'generating' || data.status === 'retrying') {
                setCadData({ format: 'loading' });
                setShowCadWindow(true);
                if (data.status === 'generating' && data.attempt === 1) {
                    setCadThoughts(''); // Clear previous thoughts for new generation
                }
                // Auto-show the window, clamped to viewport
                if (!elementPositions.cad) {
                    const size = { w: 400, h: 400 };
                    const clamped = clampToViewport({ x: window.innerWidth / 2 + 150, y: window.innerHeight / 2 }, size);
                    setElementPositions(prev => ({
                        ...prev,
                        cad: clamped
                    }));
                }
            } else if (data.status === 'failed') {
                // Keep loading state but show error
                setCadData({ format: 'loading' });
            }
        });
        socket.on('cad_thought', (data) => {
            // Append streaming thought text
            setCadThoughts(prev => prev + data.text);
        });
        socket.on('browser_frame', (data) => {
            setBrowserData(prev => ({
                image: data.image,
                logs: [...prev.logs, data.log].filter(l => l).slice(-50) // Keep last 50 logs
            }));
            setShowBrowserWindow(true);
            // Auto-show browser window if hidden, clamped to viewport
            if (!elementPositions.browser) {
                const size = { w: 550, h: 380 };
                const clamped = clampToViewport({ x: window.innerWidth / 2 - 200, y: window.innerHeight / 2 }, size);
                setElementPositions(prev => ({
                    ...prev,
                    browser: clamped
                }));
            }
        });

        // Handle streaming transcription
        socket.on('transcription', (data) => {
            setMessages(prev => {
                const lastMsg = prev[prev.length - 1];

                // If the last message is from the same sender, append the chunk
                if (lastMsg && lastMsg.sender === data.sender) {
                    // Create a NEW object instead of mutating (prevents React StrictMode duplication)
                    return [
                        ...prev.slice(0, -1),
                        {
                            ...lastMsg,
                            text: lastMsg.text + data.text
                        }
                    ];
                } else {
                    // New message block
                    return [...prev, {
                        sender: data.sender,
                        text: data.text,
                        time: new Date().toLocaleTimeString()
                    }];
                }
            });
        });

        // Handle tool confirmation requests
        socket.on('tool_confirmation_request', (data) => {
            console.log("Received Confirmation Request:", data);
            setConfirmationRequest(data);
        });

        // Handle Print Window Request (from CadWindow)
        socket.on('request_print_window', () => {
            setShowPrinterWindow(true);
            const size = { w: 380, h: 380 };
            const clamped = clampToViewport({ x: window.innerWidth / 2, y: window.innerHeight / 2 }, size);
            setElementPositions(prev => ({
                ...prev,
                printer: clamped
            }));
        });

        // Kasa Devices
        socket.on('kasa_devices', (devices) => {
            console.log("Kasa Devices:", devices);
            setKasaDevices(devices);
        });

        socket.on('kasa_update', (data) => {
            setKasaDevices(prev => prev.map(d => {
                if (d.ip === data.ip) {
                    // Update only fields that are not null/undefined
                    return {
                        ...d,
                        is_on: data.is_on !== null ? data.is_on : d.is_on,
                        brightness: data.brightness !== null ? data.brightness : d.brightness
                    };
                }
                return d;
            }));
        });

        socket.on('project_update', (data) => {
            console.log("Project Update:", data.project);
            setCurrentProject(data.project);
            addMessage('System', `Switched to project: ${data.project}`);
        });

        // Track printer count for toolbar display
        socket.on('printer_list', (list) => {
            console.log('[PRINTERS] Count:', list.length);
            setPrinterCount(list.length);
        });

        // Slicing progress for top toolbar
        socket.on('slicing_progress', (data) => {
            console.log('[SLICING] Progress:', data);
            setSlicingStatus({
                active: data.percent < 100,
                percent: data.percent,
                message: data.message
            });
        });

        // Print status for top toolbar - track active prints
        socket.on('print_status_update', (data) => {
            console.log('[PRINT STATUS]', data);
            // Only show in toolbar if actively printing
            if (data.state && data.state.toLowerCase().includes('print')) {
                setActivePrintStatus({
                    printer: data.printer,
                    progress_percent: data.progress_percent,
                    time_elapsed: data.time_elapsed,
                    state: data.state
                });
            } else if (data.state && (data.state.toLowerCase() === 'idle' || data.state.toLowerCase() === 'standby' || data.state.toLowerCase() === 'complete')) {
                // Clear if print finished or idle
                setActivePrintStatus(null);
            }
        });



        // Get All Media Devices (Microphones, Speakers, Webcams)
        navigator.mediaDevices.enumerateDevices().then(devs => {
            const audioInputs = devs.filter(d => d.kind === 'audioinput');
            const audioOutputs = devs.filter(d => d.kind === 'audiooutput');
            const videoInputs = devs.filter(d => d.kind === 'videoinput');

            setMicDevices(audioInputs);
            setSpeakerDevices(audioOutputs);
            setWebcamDevices(videoInputs);

            // Restore saved microphone or use first available
            const savedMicId = localStorage.getItem('selectedMicId');
            if (savedMicId && audioInputs.some(d => d.deviceId === savedMicId)) {
                setSelectedMicId(savedMicId);
            } else if (audioInputs.length > 0) {
                setSelectedMicId(audioInputs[0].deviceId);
            }

            // Restore saved speaker or use first available
            const savedSpeakerId = localStorage.getItem('selectedSpeakerId');
            if (savedSpeakerId && audioOutputs.some(d => d.deviceId === savedSpeakerId)) {
                setSelectedSpeakerId(savedSpeakerId);
            } else if (audioOutputs.length > 0) {
                setSelectedSpeakerId(audioOutputs[0].deviceId);
            }

            // Restore saved webcam or use first available
            const savedWebcamId = localStorage.getItem('selectedWebcamId');
            if (savedWebcamId && videoInputs.some(d => d.deviceId === savedWebcamId)) {
                setSelectedWebcamId(savedWebcamId);
            } else if (videoInputs.length > 0) {
                setSelectedWebcamId(videoInputs[0].deviceId);
            }
        });

        // Initialize Hand Landmarker
        const initHandLandmarker = async () => {
            if (globalHandLandmarker && globalFaceLandmarker) {
                console.log("Landmark Trackers already initialized globally. Reusing...");
                handLandmarkerRef.current = globalHandLandmarker;
                faceLandmarkerRef.current = globalFaceLandmarker;
                addMessage('System', 'Motion Tracking Ready');
                return;
            }
            if (globalHandLandmarkerPromise) {
                console.log("Landmark Trackers initialization already in progress. Waiting...");
                try {
                    const trackers = await globalHandLandmarkerPromise;
                    handLandmarkerRef.current = trackers.handLandmarker;
                    faceLandmarkerRef.current = trackers.faceLandmarker;
                    addMessage('System', 'Motion Tracking Ready');
                } catch (error) {
                    console.error("Failed to await existing trackers promise:", error);
                }
                return;
            }

            try {
                console.log("Initializing Landmark Trackers...");

                globalHandLandmarkerPromise = (async () => {
                    // 1. Verify Model Files
                    console.log("Fetching model files...");
                    const [handResp, faceResp] = await Promise.all([
                        fetch('/hand_landmarker.task'),
                        fetch('/face_landmarker.task')
                    ]);
                    if (!handResp.ok) throw new Error(`Failed to fetch hand landmarker: ${handResp.status}`);
                    if (!faceResp.ok) throw new Error(`Failed to fetch face landmarker: ${faceResp.status}`);

                    // 2. Initialize Vision
                    console.log("Initializing FilesetResolver...");
                    const vision = await FilesetResolver.forVisionTasks(
                        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm"
                    );
                    console.log("FilesetResolver initialized.");

                    // 3. Create Landmarkes
                    console.log("Creating HandLandmarker & FaceLandmarker (GPU)...");
                    const [handLandmarker, faceLandmarker] = await Promise.all([
                        HandLandmarker.createFromOptions(vision, {
                            baseOptions: {
                                modelAssetPath: `/hand_landmarker.task`,
                                delegate: "GPU"
                            },
                            runningMode: "VIDEO",
                            numHands: 1
                        }),
                        FaceLandmarker.createFromOptions(vision, {
                            baseOptions: {
                                modelAssetPath: `/face_landmarker.task`,
                                delegate: "GPU"
                            },
                            runningMode: "VIDEO",
                            outputFaceBlendshapes: false,
                            outputFacialTransformationMatrixes: false
                        })
                    ]);

                    return { handLandmarker, faceLandmarker };
                })();

                const trackers = await globalHandLandmarkerPromise;
                handLandmarkerRef.current = trackers.handLandmarker;
                faceLandmarkerRef.current = trackers.faceLandmarker;
                console.log("Landmark Trackers initialized successfully!");
                addMessage('System', 'Motion Tracking Ready');

            } catch (error) {
                console.error("Failed to initialize Landmark Trackers:", error);
                addMessage('System', `Motion Tracking Error: ${error.message}`);
                globalHandLandmarkerPromise = null;
            }
        };
        initHandLandmarker();

        return () => {
            socket.off('connect');
            socket.off('disconnect');
            socket.off('status');
            socket.off('audio_data');
            socket.off('auth_status');
            socket.off('settings');
            socket.off('cad_data');
            socket.off('cad_thought');
            socket.off('cad_status');
            socket.off('browser_frame');
            socket.off('transcription');
            socket.off('tool_confirmation_request');
            socket.off('request_print_window');
            socket.off('kasa_devices');
            socket.off('kasa_update');
            socket.off('project_update');
            socket.off('printer_list');
            socket.off('slicing_progress');
            socket.off('print_status_update');
            socket.off('overload_state');
            socket.off('error');

            stopMicVisualizer();
            stopVideo();
        };
    }, []);

    // Initial check in case we are already connected (fix race condition)
    useEffect(() => {
        if (socket.connected) {
            setStatus('Connected');
            socket.emit('get_settings');
        }
    }, []);

    // Persist device selections to localStorage when they change
    useEffect(() => {
        if (selectedMicId) {
            localStorage.setItem('selectedMicId', selectedMicId);
            console.log('[Settings] Saved microphone:', selectedMicId);
        }
    }, [selectedMicId]);

    useEffect(() => {
        if (selectedSpeakerId) {
            localStorage.setItem('selectedSpeakerId', selectedSpeakerId);
            console.log('[Settings] Saved speaker:', selectedSpeakerId);
        }
    }, [selectedSpeakerId]);

    useEffect(() => {
        if (selectedWebcamId) {
            localStorage.setItem('selectedWebcamId', selectedWebcamId);
            console.log('[Settings] Saved webcam:', selectedWebcamId);
        }
    }, [selectedWebcamId]);

    // Start/Stop Mic Visualizer
    useEffect(() => {
        if (selectedMicId) {
            startMicVisualizer(selectedMicId);
        }
    }, [selectedMicId]);

    const startMicVisualizer = async (deviceId) => {
        stopMicVisualizer();
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: { deviceId: { exact: deviceId } }
            });

            audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
            analyserRef.current = audioContextRef.current.createAnalyser();
            analyserRef.current.fftSize = 64;

            sourceRef.current = audioContextRef.current.createMediaStreamSource(stream);
            sourceRef.current.connect(analyserRef.current);

            const updateMicData = () => {
                if (!analyserRef.current) return;
                const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
                analyserRef.current.getByteFrequencyData(dataArray);
                setMicAudioData(Array.from(dataArray));
                animationFrameRef.current = requestAnimationFrame(updateMicData);
            };

            updateMicData();
        } catch (err) {
            console.error("Error accessing microphone:", err);
        }
    };

    const stopMicVisualizer = () => {
        if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
        if (sourceRef.current) sourceRef.current.disconnect();
        if (audioContextRef.current) audioContextRef.current.close();
    };

    const startVideo = async () => {
        try {
            // Request 1080p resolution with selected webcam
            const constraints = {
                video: {
                    width: { ideal: 1920 },
                    height: { ideal: 1080 },
                    aspectRatio: 16 / 9
                }
            };

            // Use selected webcam if available
            if (selectedWebcamId) {
                constraints.video.deviceId = { exact: selectedWebcamId };
            }

            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                videoRef.current.play();
            }

            // Initialize the transmission canvas
            if (!transmissionCanvasRef.current) {
                transmissionCanvasRef.current = document.createElement('canvas');
                transmissionCanvasRef.current.width = 640;
                transmissionCanvasRef.current.height = 360;
                console.log("Initialized transmission canvas (640x360)");
            }

            setIsVideoOn(true);
            isVideoOnRef.current = true; // Update ref for loop

            console.log("Starting video loop with webcam:", selectedWebcamId || "default");
            requestAnimationFrame(predictWebcam);

        } catch (err) {
            console.error("Error accessing camera:", err);
            addMessage('System', 'Error accessing camera');
        }
    };

    const predictWebcam = () => {
        // Use ref for checking state to avoid closure staleness
        if (!videoRef.current || !canvasRef.current || !isVideoOnRef.current) {
            return;
        }

        // Check if video has valid dimensions to prevent MediaPipe crash
        if (videoRef.current.readyState < 2 || videoRef.current.videoWidth === 0 || videoRef.current.videoHeight === 0) {
            requestAnimationFrame(predictWebcam);
            return;
        }

        // 1. Draw Video to Local Display Canvas (Native Resolution)
        const ctx = canvasRef.current.getContext('2d');

        // Ensure canvas matches video dimensions
        if (canvasRef.current.width !== videoRef.current.videoWidth || canvasRef.current.height !== videoRef.current.videoHeight) {
            canvasRef.current.width = videoRef.current.videoWidth;
            canvasRef.current.height = videoRef.current.videoHeight;
        }

        ctx.drawImage(videoRef.current, 0, 0, canvasRef.current.width, canvasRef.current.height);

        // Run Object Detection (throttled every 3 frames)
        if (cocoModel && frameCountRef.current % 3 === 0) {
            cocoModel.detect(videoRef.current)
                .then(predictions => {
                    latestPredictionsRef.current = predictions;
                })
                .catch(err => {
                    console.error("COCO-SSD detection error:", err);
                });
        }

        // 2. Send Frame to Backend (Throttled & Resized)
        // Only send if connected
        if (isConnected) {
            // Simple throttle: every 5th frame roughly
            if (frameCountRef.current % 5 === 0) {

                // Use dedicated transmission canvas for resizing
                const transCanvas = transmissionCanvasRef.current;
                if (transCanvas) {
                    const transCtx = transCanvas.getContext('2d');
                    // Draw resized image
                    transCtx.drawImage(videoRef.current, 0, 0, transCanvas.width, transCanvas.height);

                    // Convert resized image to blob
                    transCanvas.toBlob((blob) => {
                        if (blob) {
                            socket.emit('video_frame', { image: blob });
                        }
                    }, 'image/jpeg', 0.6); // Slightly higher compression for speed
                }
            }
        }


        // 3. Eye & Hand Motion Tracking HUD
        let startTimeMs = performance.now();

        // Perform Hand Detection (Runs when new webcam frame is available)
        if (handLandmarkerRef.current && videoRef.current.currentTime !== lastVideoTimeRef.current) {
            lastVideoTimeRef.current = videoRef.current.currentTime;
            const results = handLandmarkerRef.current.detectForVideo(videoRef.current, startTimeMs);

            if (results.landmarks && results.landmarks.length > 0) {
                latestHandLandmarksRef.current = results.landmarks[0];

                // Execute OS cursor control ONLY if Hand Gesture Controls are enabled in settings
                if (isHandTrackingEnabledRef.current) {
                    const indexTip = latestHandLandmarksRef.current[8];
                    const thumbTip = latestHandLandmarksRef.current[4];

                    const SENSITIVITY = cursorSensitivityRef.current;
                    const rawX = 1 - indexTip.x;

                    let normX = (rawX - 0.5) * SENSITIVITY + 0.5;
                    normX = Math.max(0, Math.min(1, normX));

                    let normY = (indexTip.y - 0.5) * SENSITIVITY + 0.5;
                    normY = Math.max(0, Math.min(1, normY));

                    const targetX = normX * window.innerWidth;
                    const targetY = normY * window.innerHeight;

                    const lerpFactor = 0.2;
                    smoothedCursorPosRef.current.x = smoothedCursorPosRef.current.x + (targetX - smoothedCursorPosRef.current.x) * lerpFactor;
                    smoothedCursorPosRef.current.y = smoothedCursorPosRef.current.y + (targetY - smoothedCursorPosRef.current.y) * lerpFactor;

                    let finalX = smoothedCursorPosRef.current.x;
                    let finalY = smoothedCursorPosRef.current.y;

                    const SNAP_THRESHOLD = 50;
                    const UNSNAP_THRESHOLD = 100;

                    if (snapStateRef.current.isSnapped) {
                        const dist = Math.sqrt(
                            Math.pow(finalX - snapStateRef.current.snapPos.x, 2) +
                            Math.pow(finalY - snapStateRef.current.snapPos.y, 2)
                        );

                        if (dist > UNSNAP_THRESHOLD) {
                            if (snapStateRef.current.element) {
                                snapStateRef.current.element.classList.remove('snap-highlight');
                                snapStateRef.current.element.style.boxShadow = '';
                                snapStateRef.current.element.style.backgroundColor = '';
                                snapStateRef.current.element.style.borderColor = '';
                            }
                            snapStateRef.current = { isSnapped: false, element: null, snapPos: { x: 0, y: 0 } };
                        } else {
                            finalX = snapStateRef.current.snapPos.x;
                            finalY = snapStateRef.current.snapPos.y;
                        }
                    } else {
                        const targets = Array.from(document.querySelectorAll('button, input, select, .draggable'));
                        let closest = null;
                        let minDist = Infinity;

                        for (const el of targets) {
                            const rect = el.getBoundingClientRect();
                            const centerX = rect.left + rect.width / 2;
                            const centerY = rect.top + rect.height / 2;
                            const dist = Math.sqrt(Math.pow(finalX - centerX, 2) + Math.pow(finalY - centerY, 2));

                            if (dist < minDist) {
                                minDist = dist;
                                closest = { el, centerX, centerY };
                            }
                        }

                        if (closest && minDist < SNAP_THRESHOLD) {
                            snapStateRef.current = {
                                isSnapped: true,
                                element: closest.el,
                                snapPos: { x: closest.centerX, y: closest.centerY }
                            };
                            finalX = closest.centerX;
                            finalY = closest.centerY;

                            closest.el.classList.add('snap-highlight');
                            closest.el.style.boxShadow = '0 0 20px rgba(34, 211, 238, 0.6)';
                            closest.el.style.backgroundColor = 'rgba(6, 182, 212, 0.2)';
                            closest.el.style.borderColor = 'rgba(34, 211, 238, 1)';
                        }
                    }

                    setCursorPos({ x: finalX, y: finalY });

                    const distance = Math.sqrt(
                        Math.pow(indexTip.x - thumbTip.x, 2) + Math.pow(indexTip.y - thumbTip.y, 2)
                    );

                    const isPinchNow = distance < 0.05;
                    if (isPinchNow && !isPinching) {
                        const el = document.elementFromPoint(finalX, finalY);
                        if (el) {
                            const clickable = el.closest('button, input, a, [role="button"]');
                            if (clickable && typeof clickable.click === 'function') {
                                clickable.click();
                            } else if (typeof el.click === 'function') {
                                el.click();
                            }
                        }
                    }
                    setIsPinching(isPinchNow);

                    const isFingerFolded = (tipIdx, mcpIdx) => {
                        const tip = latestHandLandmarksRef.current[tipIdx];
                        const mcp = latestHandLandmarksRef.current[mcpIdx];
                        const wrist = latestHandLandmarksRef.current[0];
                        const distTip = Math.sqrt(Math.pow(tip.x - wrist.x, 2) + Math.pow(tip.y - wrist.y, 2));
                        const distMcp = Math.sqrt(Math.pow(mcp.x - wrist.x, 2) + Math.pow(mcp.y - wrist.y, 2));
                        return distTip < distMcp;
                    };

                    const isFist = isFingerFolded(8, 5) && isFingerFolded(12, 9) && isFingerFolded(16, 13) && isFingerFolded(20, 17);

                    const wrist = latestHandLandmarksRef.current[0];
                    const wristRawX = 1 - wrist.x;
                    const wristNormX = Math.max(0, Math.min(1, (wristRawX - 0.5) * SENSITIVITY + 0.5));
                    const wristNormY = Math.max(0, Math.min(1, (wrist.y - 0.5) * SENSITIVITY + 0.5));
                    const wristScreenX = wristNormX * window.innerWidth;
                    const wristScreenY = wristNormY * window.innerHeight;

                    if (isFist) {
                        if (!activeDragElementRef.current) {
                            const draggableElements = ['cad', 'browser', 'kasa', 'printer'];
                            for (const id of draggableElements) {
                                const el = document.getElementById(id);
                                if (el) {
                                    const rect = el.getBoundingClientRect();
                                    if (finalX >= rect.left && finalX <= rect.right && finalY >= rect.top && finalY <= rect.bottom) {
                                        activeDragElementRef.current = id;
                                        bringToFront(id);
                                        lastWristPosRef.current = { x: wristScreenX, y: wristScreenY };
                                        break;
                                    }
                                }
                            }
                        }

                        if (activeDragElementRef.current) {
                            const dx = wristScreenX - lastWristPosRef.current.x;
                            const dy = wristScreenY - lastWristPosRef.current.y;
                            if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
                                updateElementPosition(activeDragElementRef.current, dx, dy);
                            }
                            lastWristPosRef.current = { x: wristScreenX, y: wristScreenY };
                        }
                    } else {
                        activeDragElementRef.current = null;
                    }

                    if (activeDragElementRef.current !== lastActiveDragElementRef.current) {
                        setActiveDragElement(activeDragElementRef.current);
                        lastActiveDragElementRef.current = activeDragElementRef.current;
                    }

                    lastCursorPosRef.current = { x: finalX, y: finalY };
                }
            } else {
                latestHandLandmarksRef.current = null;
            }
        }

        // Perform Face Detection (Runs when new webcam frame is available)
        if (faceLandmarkerRef.current && videoRef.current.currentTime !== lastFaceVideoTimeRef.current) {
            lastFaceVideoTimeRef.current = videoRef.current.currentTime;
            const faceResults = faceLandmarkerRef.current.detectForVideo(videoRef.current, startTimeMs);

            if (faceResults.faceLandmarks && faceResults.faceLandmarks.length > 0) {
                latestFaceLandmarksRef.current = faceResults.faceLandmarks[0];
            } else {
                latestFaceLandmarksRef.current = null;
            }
        }

        // Render HUD Overlays (Runs EVERY frame so drawing isn't overwritten by ctx.drawImage)
        if (latestHandLandmarksRef.current) {
            drawSkeleton(ctx, latestHandLandmarksRef.current);
            drawHandReticle(ctx, latestHandLandmarksRef.current);
        }
        if (latestFaceLandmarksRef.current) {
            drawEyeTracking(ctx, latestFaceLandmarksRef.current, latestHandLandmarksRef.current);
        }
        if (latestPredictionsRef.current && latestPredictionsRef.current.length > 0) {
            drawObjectDetections(ctx, latestPredictionsRef.current);
        }

        // 4. FPS Calculation
        const now = performance.now();
        frameCountRef.current++;
        if (now - lastFrameTimeRef.current >= 1000) {
            setFps(frameCountRef.current);
            frameCountRef.current = 0;
            lastFrameTimeRef.current = now;
        }

        if (isVideoOnRef.current) {
            requestAnimationFrame(predictWebcam);
        }
    };

    const drawSkeleton = (ctx, landmarks) => {
        ctx.strokeStyle = '#00FFFF';
        ctx.lineWidth = 2;

        // Connections
        const connections = HandLandmarker.HAND_CONNECTIONS;
        for (const connection of connections) {
            const start = landmarks[connection.start];
            const end = landmarks[connection.end];
            ctx.beginPath();
            ctx.moveTo(start.x * canvasRef.current.width, start.y * canvasRef.current.height);
            ctx.lineTo(end.x * canvasRef.current.width, end.y * canvasRef.current.height);
            ctx.stroke();
        }
    };

    const drawEyeTracking = (ctx, faceLandmarks, handLandmarks) => {
        if (!canvasRef.current || faceLandmarks.length < 468) return;

        const cw = canvasRef.current.width;
        const ch = canvasRef.current.height;

        // Retrieve pupil centers (468 for Left Eye pupil, 473 for Right Eye pupil)
        const leftPupil = faceLandmarks[468] || faceLandmarks[33];
        const rightPupil = faceLandmarks[473] || faceLandmarks[263];

        const lx = leftPupil.x * cw;
        const ly = leftPupil.y * ch;
        const rx = rightPupil.x * cw;
        const ry = rightPupil.y * ch;

        ctx.lineWidth = 1;

        // 1. Left Eye HUD Reticle
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.75)'; // Neon Cyan
        ctx.beginPath();
        ctx.arc(lx, ly, 10, 0, 2 * Math.PI);
        ctx.stroke();

        ctx.strokeStyle = 'rgba(6, 182, 212, 0.45)';
        ctx.beginPath();
        ctx.arc(lx, ly, 16, 0, 2 * Math.PI);
        ctx.stroke();

        // Left Crosshairs
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.85)';
        ctx.beginPath();
        ctx.moveTo(lx - 20, ly); ctx.lineTo(lx - 6, ly);
        ctx.moveTo(lx + 6, ly); ctx.lineTo(lx + 20, ly);
        ctx.moveTo(lx, ly - 20); ctx.lineTo(lx, ly - 6);
        ctx.moveTo(lx, ly + 6); ctx.lineTo(lx, ly + 20);
        ctx.stroke();

        // Pupil Dot
        ctx.fillStyle = 'rgba(34, 211, 238, 0.9)';
        ctx.beginPath();
        ctx.arc(lx, ly, 2, 0, 2 * Math.PI);
        ctx.fill();

        // Left Telemetry Label
        ctx.fillStyle = 'rgba(34, 211, 238, 0.85)';
        ctx.font = '8px monospace';
        ctx.fillText(`L_EYE // [X:${leftPupil.x.toFixed(2)} Y:${leftPupil.y.toFixed(2)}]`, lx + 24, ly - 6);

        // 2. Right Eye HUD Reticle
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.75)';
        ctx.beginPath();
        ctx.arc(rx, ry, 10, 0, 2 * Math.PI);
        ctx.stroke();

        ctx.strokeStyle = 'rgba(6, 182, 212, 0.45)';
        ctx.beginPath();
        ctx.arc(rx, ry, 16, 0, 2 * Math.PI);
        ctx.stroke();

        // Right Crosshairs
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.85)';
        ctx.beginPath();
        ctx.moveTo(rx - 20, ry); ctx.lineTo(rx - 6, ry);
        ctx.moveTo(rx + 6, ry); ctx.lineTo(rx + 20, ry);
        ctx.moveTo(rx, ry - 20); ctx.lineTo(rx, ry - 6);
        ctx.moveTo(rx, ry + 6); ctx.lineTo(rx, ry + 20);
        ctx.stroke();

        // Pupil Dot
        ctx.fillStyle = 'rgba(34, 211, 238, 0.9)';
        ctx.beginPath();
        ctx.arc(rx, ry, 2, 0, 2 * Math.PI);
        ctx.fill();

        // Right Telemetry Label
        ctx.fillStyle = 'rgba(34, 211, 238, 0.85)';
        ctx.font = '8px monospace';
        ctx.fillText(`R_EYE // [X:${rightPupil.x.toFixed(2)} Y:${rightPupil.y.toFixed(2)}]`, rx + 24, ry - 6);

        // 3. Connect Eyes Baseline
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.2)';
        ctx.beginPath();
        ctx.moveTo(lx, ly);
        ctx.lineTo(rx, ry);
        ctx.stroke();

        // 4. Coordination Laser Line (if hand is visible)
        if (handLandmarks && handLandmarks.length > 8) {
            const hx = handLandmarks[8].x * cw;
            const hy = handLandmarks[8].y * ch;

            ctx.strokeStyle = 'rgba(239, 68, 68, 0.55)'; // Neon Red
            ctx.lineWidth = 1;
            ctx.setLineDash([3, 4]);
            ctx.beginPath();
            ctx.moveTo(lx, ly);
            ctx.lineTo(hx, hy);
            ctx.moveTo(rx, ry);
            ctx.lineTo(hx, hy);
            ctx.stroke();
            ctx.setLineDash([]); // Reset

            const midX = (lx + hx) / 2;
            const midY = (ly + hy) / 2;
            ctx.fillStyle = 'rgba(248, 113, 113, 0.9)';
            ctx.fillText(`COOR_LINK // SYNC`, midX + 10, midY);
        }
    };

    const drawHandReticle = (ctx, landmarks) => {
        if (!canvasRef.current || landmarks.length < 9) return;

        const cw = canvasRef.current.width;
        const ch = canvasRef.current.height;

        const ix = landmarks[8].x * cw;
        const iy = landmarks[8].y * ch;

        // Concentric target rings on index tip
        ctx.strokeStyle = 'rgba(34, 211, 238, 0.8)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(ix, iy, 7, 0, 2 * Math.PI);
        ctx.stroke();

        ctx.strokeStyle = 'rgba(34, 211, 238, 0.4)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(ix, iy, 13, 0, 2 * Math.PI);
        ctx.stroke();

        // Ticks
        ctx.strokeStyle = 'rgba(34, 211, 238, 0.7)';
                    ctx.beginPath();
        ctx.moveTo(ix - 16, iy); ctx.lineTo(ix - 10, iy);
        ctx.moveTo(ix + 10, iy); ctx.lineTo(ix + 16, iy);
        ctx.moveTo(ix, iy - 16); ctx.lineTo(ix, iy - 10);
        ctx.moveTo(ix, iy + 10); ctx.lineTo(ix, iy + 16);
        ctx.stroke();

        // Pointer coords text
        ctx.fillStyle = 'rgba(34, 211, 238, 0.85)';
        ctx.font = '8px monospace';
        ctx.fillText(`PTR // [X:${landmarks[8].x.toFixed(2)} Y:${landmarks[8].y.toFixed(2)}]`, ix + 18, iy - 4);
    };

    const drawObjectDetections = (ctx, predictions) => {
        if (!predictions || predictions.length === 0 || !canvasRef.current) return;
        
        const cw = canvasRef.current.width;
        const ch = canvasRef.current.height;
        const vw = videoRef.current.videoWidth;
        const vh = videoRef.current.videoHeight;
        
        const scaleX = cw / vw;
        const scaleY = ch / vh;
        
        predictions.forEach(pred => {
            const [x, y, width, height] = pred.bbox;
            const rx = x * scaleX;
            const ry = y * scaleY;
            const rw = width * scaleX;
            const rh = height * scaleY;
            
            const color = 'rgba(255, 0, 128, 0.85)'; // Cyber Magenta
            ctx.shadowColor = 'rgba(255, 0, 128, 0.7)';
            ctx.shadowBlur = 8;
            
            ctx.fillStyle = 'rgba(255, 0, 128, 0.05)';
            ctx.fillRect(rx, ry, rw, rh);
            
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            const cornerLen = Math.min(15, Math.min(rw / 4, rh / 4));
            
            // Top-Left Corner
            ctx.beginPath();
            ctx.moveTo(rx + cornerLen, ry);
            ctx.lineTo(rx, ry);
            ctx.lineTo(rx, ry + cornerLen);
            ctx.stroke();
            
            // Top-Right Corner
            ctx.beginPath();
            ctx.moveTo(rx + rw - cornerLen, ry);
            ctx.lineTo(rx + rw, ry);
            ctx.lineTo(rx + rw, ry + cornerLen);
            ctx.stroke();
            
            // Bottom-Left Corner
            ctx.beginPath();
            ctx.moveTo(rx + cornerLen, ry + rh);
            ctx.lineTo(rx, ry + rh);
            ctx.lineTo(rx, ry + rh - cornerLen);
            ctx.stroke();
            
            // Bottom-Right Corner
            ctx.beginPath();
            ctx.moveTo(rx + rw - cornerLen, ry + rh);
            ctx.lineTo(rx + rw, ry + rh);
            ctx.lineTo(rx + rw, ry + rh - cornerLen);
            ctx.stroke();
            
            // Dashed outline
            ctx.strokeStyle = 'rgba(255, 0, 128, 0.25)';
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);
            ctx.strokeRect(rx, ry, rw, rh);
            ctx.setLineDash([]);
            
            ctx.shadowBlur = 0;
            
            // Center crosshair
            const cx = rx + rw / 2;
            const cy = ry + rh / 2;
            ctx.strokeStyle = 'rgba(0, 255, 255, 0.5)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(cx - 5, cy); ctx.lineTo(cx + 5, cy);
            ctx.moveTo(cx, cy - 5); ctx.lineTo(cx, cy + 5);
            ctx.stroke();
            
            // Telemetry Tag
            ctx.fillStyle = 'rgba(0, 255, 255, 0.85)';
            ctx.font = '9px monospace';
            const label = `[ OBJ: ${pred.class.toUpperCase()} // CONF: ${Math.round(pred.score * 100)}% ]`;
            
            const textWidth = ctx.measureText(label).width;
            ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
            ctx.fillRect(rx, ry - 14, textWidth + 8, 14);
            
            ctx.strokeStyle = 'rgba(0, 255, 255, 0.5)';
            ctx.lineWidth = 1;
            ctx.strokeRect(rx, ry - 14, textWidth + 8, 14);
            
            ctx.fillStyle = 'rgba(0, 255, 255, 0.95)';
            ctx.fillText(label, rx + 4, ry - 4);
        });
    };

    const stopVideo = () => {
        if (videoRef.current && videoRef.current.srcObject) {
            videoRef.current.srcObject.getTracks().forEach(track => track.stop());
            videoRef.current.srcObject = null;
        }
        setIsVideoOn(false);
        isVideoOnRef.current = false; // Update ref
        setFps(0);
    };

    const toggleVideo = () => {
        if (isVideoOn) {
            stopVideo();
        } else {
            startVideo();
        }
    };

    const addMessage = (sender, text) => {
        setMessages(prev => [...prev, { sender, text, time: new Date().toLocaleTimeString() }]);
    };

    const togglePower = () => {
        if (isConnected) {
            socket.emit('stop_text_chat');
            setIsConnected(false);
            setIsMuted(false); // Reset mute state
        } else {
            socket.emit('start_text_chat');
            setIsConnected(true);
            setIsMuted(false); // Start unmuted
        }
    };

    const toggleMute = () => {
        if (!isConnected) return; // Can't mute if not connected

        if (isMuted) {
            socket.emit('resume_audio');
            setIsMuted(false);
        } else {
            socket.emit('pause_audio');
            setIsMuted(true);
        }
    };

    const handleSend = (e) => {
        if (e.key === 'Enter' && inputValue.trim()) {
            socket.emit('user_input', { text: inputValue });
            addMessage('You', inputValue);
            setInputValue('');
        }
    };

    const handleMinimize = () => ipcRenderer.send('window-minimize');
    const handleMaximize = () => ipcRenderer.send('window-maximize');

    // Close Application - memory is now actively saved to project, no prompt needed
    const handleCloseRequest = () => {
        // Emit shutdown signal to backend for graceful shutdown
        // Use volatile emit with timeout fallback to ensure window closes even if server is unresponsive
        const closeWindow = () => ipcRenderer.send('window-close');

        if (socket.connected) {
            console.log('[APP] Sending shutdown signal to backend...');
            socket.emit('shutdown', {}, (ack) => {
                // This callback may not be called if server uses os._exit
                console.log('[APP] Shutdown acknowledged');
                closeWindow();
            });
            // Fallback: close after 500ms if ack doesn't come back
            setTimeout(closeWindow, 500);
        } else {
            // Socket not connected, just close
            closeWindow();
        }
    };

    // handleCancelClose removed - no longer using memory prompt

    const handleConfirmTool = () => {
        if (confirmationRequest) {
            socket.emit('confirm_tool', { id: confirmationRequest.id, confirmed: true });
            setConfirmationRequest(null);
        }
    };

    const handleDenyTool = () => {
        if (confirmationRequest) {
            socket.emit('confirm_tool', { id: confirmationRequest.id, confirmed: false });
            setConfirmationRequest(null);
        }
    };

    // Updated Bounds Checking Logic
    const updateElementPosition = (id, dx, dy) => {
        setElementPositions(prev => {
            const currentPos = prev[id];
            const size = elementSizes[id] || { w: 100, h: 100 }; // Fallback
            let newX = currentPos.x + dx;
            let newY = currentPos.y + dy;

            // Bounds Logic
            // Depends on anchor point.
            // Visualizer, Tools, Cad, Browser, Kasa: translate(-50%, -50%) -> Center Anchor
            // Chat: translate(-50%, 0) -> Top-Center Anchor
            // Video: Top-Left Anchor (default div)

            const width = window.innerWidth;
            const height = window.innerHeight;
            const margin = 0; // Strict bounds

            if (id === 'chat') {
                // Anchor: Top-Center (x is center, y is top)
                // X Bounds: size.w/2 <= x <= width - size.w/2
                newX = Math.max(size.w / 2 + margin, Math.min(width - size.w / 2 - margin, newX));
                // Y Bounds: 0 <= y <= height - size.h
                newY = Math.max(margin, Math.min(height - size.h - margin, newY));

            } else if (id === 'video') {
                // Anchor: Top-Left
                newX = Math.max(margin, Math.min(width - size.w - margin, newX));
                newY = Math.max(margin, Math.min(height - size.h - margin, newY));

            } else {
                // Anchor: Center
                newX = Math.max(size.w / 2 + margin, Math.min(width - size.w / 2 - margin, newX));
                newY = Math.max(size.h / 2 + margin, Math.min(height - size.h / 2 - margin, newY));
            }

            return {
                ...prev,
                [id]: {
                    x: newX,
                    y: newY
                }
            };
        });
    };

    // --- MOUSE DRAG HANDLERS ---
    const handleMouseDown = (e, id) => {
        console.log(`[MouseDrag] MouseDown on ${id}`, { target: e.target.tagName });

        // Fixed elements that should never be draggable (even in modular mode)
        const fixedElements = ['visualizer', 'chat', 'video', 'tools'];
        if (fixedElements.includes(id)) {
            console.log(`[MouseDrag] ${id} is a fixed element, not draggable`);
            return;
        }

        // Bring clicked element to front (z-index)
        bringToFront(id);

        // Prevent dragging if interacting with inputs, buttons, or canvas (for 3D controls)
        const tagName = e.target.tagName.toLowerCase();
        if (tagName === 'input' || tagName === 'button' || tagName === 'textarea' || tagName === 'canvas' || e.target.closest('button')) {
            console.log("[MouseDrag] Interaction blocked by interactive element");
            return;
        }

        // Check if clicking on a drag handle section (data-drag-handle attribute)
        const isDragHandle = e.target.closest('[data-drag-handle]');
        if (!isDragHandle && !isModularModeRef.current) {
            // If not clicking a drag handle and modular mode is off, don't drag
            // This allows popup windows to have dedicated drag areas
            console.log("[MouseDrag] Not a drag handle and modular mode off");
            return;
        }

        const elPos = elementPositions[id];
        if (!elPos) return;

        // Calculate offset based on anchor point
        // Most are Center Anchored (x, y is center)
        // Chat is Top-Center Anchored (x is center, y is top)
        // Video is Top-Left Anchored (x is left, y is top)

        // We want: MousePos = ElementPos + Offset
        // So: Offset = MousePos - ElementPos
        dragOffsetRef.current = {
            x: e.clientX - elPos.x,
            y: e.clientY - elPos.y
        };

        setActiveDragElement(id);
        activeDragElementRef.current = id;
        isDraggingRef.current = true;

        window.addEventListener('mousemove', handleMouseDrag);
        window.addEventListener('mouseup', handleMouseUp);
    };

    const handleMouseDrag = (e) => {
        if (!isDraggingRef.current || !activeDragElementRef.current) return;

        const id = activeDragElementRef.current;
        const currentPos = elementPositionsRef.current[id];
        if (!currentPos) return;

        // Target Position = MousePos - Offset
        // But we want delta for updateElementPosition??
        // actually updateElementPosition takes dx, dy.
        // Let's just set the position directly or calculate delta.
        // Since updateElementPosition has bounds logic, let's use it, but we need delta from PREVIOUS position?
        // OR we can refactor updateElementPosition to take absolute.
        // Let's stick to calculating new position and manually updating state with bounds logic inside a setter.

        // Actually, updateElementPosition uses setElementPositions(prev => ...).
        // Let's duplicate bounds logic for mouse drag to be precise or reuse.
        // reusing updateElementPosition requires calculating dx/dy from *current state* which might be lagging in the closure?
        // No, functional update is fine.

        // But for smooth mouse drag, absolute position is better.
        const rawNewX = e.clientX - dragOffsetRef.current.x;
        const rawNewY = e.clientY - dragOffsetRef.current.y;

        setElementPositions(prev => {
            const size = elementSizes[id] || { w: 100, h: 100 }; // Fallback
            let newX = rawNewX;
            let newY = rawNewY;

            const width = window.innerWidth;
            const height = window.innerHeight;
            const margin = 0;

            if (id === 'chat') {
                newX = Math.max(size.w / 2 + margin, Math.min(width - size.w / 2 - margin, newX));
                newY = Math.max(margin, Math.min(height - size.h - margin, newY));
            } else if (id === 'video') {
                newX = Math.max(margin, Math.min(width - size.w - margin, newX));
                newY = Math.max(margin, Math.min(height - size.h - margin, newY));
            } else {
                newX = Math.max(size.w / 2 + margin, Math.min(width - size.w / 2 - margin, newX));
                newY = Math.max(size.h / 2 + margin, Math.min(height - size.h / 2 - margin, newY));
            }

            return {
                ...prev,
                [id]: { x: newX, y: newY }
            };
        });
    };

    const handleMouseUp = () => {
        isDraggingRef.current = false;
        setActiveDragElement(null);
        activeDragElementRef.current = null;
        window.removeEventListener('mousemove', handleMouseDrag);
        window.removeEventListener('mouseup', handleMouseUp);
    };

    // Calculate Average Audio Amplitude for Background Pulse
    const audioAmp = aiAudioData.reduce((a, b) => a + b, 0) / aiAudioData.length / 255;
    const isAISpeaking = aiAudioData && aiAudioData.some(v => v > 0);
    const activeAudioData = isAISpeaking ? aiAudioData : micAudioData;
    const activeIntensity = isAISpeaking ? audioAmp : (isMuted ? 0 : micAudioData.reduce((a, b) => a + b, 0) / micAudioData.length / 255);

    const toggleKasaWindow = () => {
        if (!showKasaWindow) {
            // Maybe trigger discover instantly?
            if (kasaDevices.length === 0) socket.emit('discover_kasa');
        }
        setShowKasaWindow(!showKasaWindow);
    };

    const togglePrinterWindow = () => {
        setShowPrinterWindow(!showPrinterWindow);
    };



    return (
        <div className={`h-screen w-screen bg-black text-cyan-100 font-mono overflow-hidden flex flex-col relative selection:bg-cyan-900 selection:text-white transition-all duration-500 ${overloadActive ? 'red-alert-screen shadow-[inset_0_0_80px_rgba(239,68,68,0.35)]' : ''}`}>
            {/* Red Alert Pulsing Screen Overlay */}
            {overloadActive && (
                <div className="absolute inset-0 bg-red-950/5 border-[8px] border-red-500/25 pointer-events-none z-50 animate-pulse mix-blend-color-burn" style={{ animationDuration: '0.8s' }}></div>
            )}

            {/* --- PREMIUM UI LAYER --- */}

            {/* --- PREMIUM UI LAYER --- */}

            {/* --- PREMIUM UI LAYER --- */}



            {/* --- PREMIUM UI LAYER --- */}

            {/* Hand Cursor - Only show if tracking is enabled */}
            {isVideoOn && isHandTrackingEnabled && (
                <div
                    className={`fixed w-6 h-6 border-2 rounded-full pointer-events-none z-[100] transition-transform duration-75 ${isPinching ? 'bg-cyan-400 border-cyan-400 scale-75 shadow-[0_0_15px_rgba(34,211,238,0.8)]' : 'border-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.3)]'}`}
                    style={{
                        left: cursorPos.x,
                        top: cursorPos.y,
                        transform: 'translate(-50%, -50%)'
                    }}
                >
                    {/* Center Dot for precision */}
                    <div className="absolute top-1/2 left-1/2 w-1 h-1 bg-white rounded-full -translate-x-1/2 -translate-y-1/2" />
                </div>
            )}

            {/* Background Grid/Effects - ALIVE BACKGROUND (Fixed: Static opacity) */}
            <div
                className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-gray-900 via-black to-black z-0 pointer-events-none"
                style={{ opacity: 0.6 }}
            ></div>
            <div className="absolute inset-0 bg-[url('/noise.svg')] opacity-20 z-0 pointer-events-none mix-blend-overlay"></div>

            {/* Ambient Glow (Fixed: Static) */}
            <div
                className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-cyan-900/10 rounded-full blur-[120px] pointer-events-none"
            />

            {/* Top Bar (Draggable) */}
            <div className="z-50 flex items-center justify-between p-2 border-b border-cyan-500/20 bg-black/40 backdrop-blur-md select-none sticky top-0" style={{ WebkitAppRegion: 'drag' }}>
                <div className="flex items-center gap-4 pl-2">
                    <h1 className="text-xl font-bold tracking-[0.2em] text-cyan-400 drop-shadow-[0_0_10px_rgba(34,211,238,0.5)]">
                        A.D.A
                    </h1>
                    <div className="text-[10px] text-cyan-700 border border-cyan-900 px-1 rounded">
                        V2.0.0
                    </div>
                    {/* FPS Counter */}
                    {isVideoOn && (
                        <div className="text-[10px] text-green-500 border border-green-900 px-1 rounded ml-2">
                            FPS: {fps}
                        </div>
                    )}
                    {/* Connected Printers Count */}
                    {printerCount > 0 && (
                        <div className="flex items-center gap-1.5 text-[10px] text-green-400 border border-green-500/30 bg-green-500/10 px-2 py-0.5 rounded ml-2">
                            <Printer size={10} className="text-green-400" />
                            <span>{printerCount} Printer{printerCount !== 1 ? 's' : ''}</span>
                        </div>
                    )}
                    {/* Connected Smart Devices Count */}
                    {kasaDevices.length > 0 && (
                        <div className="flex items-center gap-1.5 text-[10px] text-yellow-400 border border-yellow-500/30 bg-yellow-500/10 px-2 py-0.5 rounded ml-2">
                            <span>💡</span>
                            <span>{kasaDevices.length} Device{kasaDevices.length !== 1 ? 's' : ''}</span>
                        </div>
                    )}
                </div>

                {/* Top Visualizer (User Mic) */}
                <div className="flex-1 flex justify-center mx-4">
                    <TopAudioBar audioData={micAudioData} />
                </div>

                <div className="flex items-center gap-2 pr-2" style={{ WebkitAppRegion: 'no-drag' }}>
                    {/* Live Clock */}
                    <div className="flex items-center gap-1.5 text-[11px] text-cyan-300/70 font-mono px-2">
                        <Clock size={12} className="text-cyan-500/50" />
                        <span>{currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <button onClick={handleMinimize} className="p-1 hover:bg-cyan-900/50 rounded text-cyan-500 transition-colors">
                        <Minus size={18} />
                    </button>
                    <button onClick={handleMaximize} className="p-1 hover:bg-cyan-900/50 rounded text-cyan-500 transition-colors">
                        <div className="w-[14px] h-[14px] border-2 border-current rounded-[2px]" />
                    </button>
                    <button onClick={handleCloseRequest} className="p-1 hover:bg-red-900/50 rounded text-red-500 transition-colors">
                        <X size={18} />
                    </button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 relative z-10 flex flex-col items-center justify-center">
                {/* Central Visualizer (AI Audio) */}
                <div
                    id="visualizer"
                    className={`absolute flex items-center justify-center transition-all duration-200 
                        backdrop-blur-xl bg-black/30 border border-white/10 shadow-2xl overflow-visible
                        ${isModularMode ? (activeDragElement === 'visualizer' ? 'ring-2 ring-green-500 bg-green-500/10' : 'ring-1 ring-yellow-500/30 bg-yellow-500/5') + ' rounded-2xl pointer-events-auto' : 'rounded-2xl pointer-events-none'}
                    `}
                    style={{
                        left: elementPositions.visualizer.x,
                        top: elementPositions.visualizer.y,
                        transform: 'translate(-50%, -50%)',
                        width: elementSizes.visualizer.w,
                        height: elementSizes.visualizer.h
                    }}
                    onMouseDown={(e) => handleMouseDown(e, 'visualizer')}
                >
                    <div className="absolute inset-0 bg-[url('/noise.svg')] opacity-10 pointer-events-none mix-blend-overlay z-10"></div>
                    <div className="relative z-20">
                        <Visualizer
                            audioData={activeAudioData}
                            isListening={isConnected && !isMuted}
                            intensity={activeIntensity}
                            width={elementSizes.visualizer.w}
                            height={elementSizes.visualizer.h}
                            overloadActive={overloadActive}
                        />
                    </div>
                    {isModularMode && <div className={`absolute top-2 right-2 text-xs font-bold tracking-widest z-20 ${activeDragElement === 'visualizer' ? 'text-green-500' : 'text-yellow-500/50'}`}>VISUALIZER</div>}
                </div>

                {/* Video Feed Overlay */}
                {/* Floating Project Label */}
                <div className="absolute top-[70px] left-1/2 -translate-x-1/2 text-cyan-500 text-xs font-mono tracking-widest pointer-events-none z-50 bg-black/50 px-2 py-1 rounded backdrop-blur-sm border border-cyan-500/20">
                    PROJECT: {currentProject?.toUpperCase()}
                </div>

                <div
                    id="video"
                    className={`fixed bottom-4 right-4 transition-all duration-200 
                        ${isVideoOn ? 'opacity-100' : 'opacity-0 pointer-events-none'} 
                        backdrop-blur-md bg-black/40 border border-white/10 shadow-xl rounded-xl
                    `}
                    style={{ zIndex: 20 }}
                >
                    <div className="absolute inset-0 bg-[url('/noise.svg')] opacity-5 pointer-events-none mix-blend-overlay"></div>
                    {/* Compact Display Container (1080p Source) */}
                    <div className="relative border border-cyan-500/30 rounded-lg overflow-hidden shadow-[0_0_20px_rgba(6,182,212,0.1)] w-80 aspect-video bg-black/80">
                        {/* Hidden Video Element (Source) */}
                        <video ref={videoRef} autoPlay muted className="absolute inset-0 w-full h-full object-cover opacity-0" />

                        <div className="absolute top-2 left-2 text-[10px] text-cyan-400 bg-black/60 backdrop-blur px-2 py-0.5 rounded border border-cyan-500/20 z-10 font-bold tracking-wider">CAM_01</div>

                        {/* Canvas for Displaying Video + Skeleton (Ensures overlap) */}
                        <canvas
                            ref={canvasRef}
                            className="absolute inset-0 w-full h-full opacity-80"
                            style={{ transform: 'scaleX(-1)' }}
                        />
                    </div>
                </div>

                {/* Settings Modal - Moved outside Video so it shows independently */}
                {showSettings && (
                    <SettingsWindow
                        socket={socket}
                        micDevices={micDevices}
                        speakerDevices={speakerDevices}
                        webcamDevices={webcamDevices}
                        selectedMicId={selectedMicId}
                        setSelectedMicId={setSelectedMicId}
                        selectedSpeakerId={selectedSpeakerId}
                        setSelectedSpeakerId={setSelectedSpeakerId}
                        selectedWebcamId={selectedWebcamId}
                        setSelectedWebcamId={setSelectedWebcamId}
                        cursorSensitivity={cursorSensitivity}
                        setCursorSensitivity={setCursorSensitivity}
                        faceAuthEnabled={faceAuthEnabled}
                        isFaceRegistered={isFaceRegistered}
                        onClose={() => setShowSettings(false)}
                    />
                )}

                {/* CAD Window Overlay - Moved outside of Video so it can show independently */}
                {showCadWindow && (
                    <div
                        id="cad"
                        className={`absolute flex flex-col transition-all duration-200 
                        backdrop-blur-xl bg-black/40 border border-white/10 shadow-2xl overflow-hidden rounded-2xl
                        ${activeDragElement === 'cad' ? 'ring-2 ring-green-500 bg-green-500/10' : ''}
                    `}
                        style={{
                            left: elementPositions.cad?.x || window.innerWidth / 2,
                            top: elementPositions.cad?.y || window.innerHeight / 2,
                            transform: 'translate(-50%, -50%)',
                            width: `${elementSizes.cad.w}px`,
                            height: `${elementSizes.cad.h}px`,
                            pointerEvents: 'auto',
                            zIndex: getZIndex('cad')
                        }}
                        onMouseDown={(e) => handleMouseDown(e, 'cad')}
                    >
                        {/* Drag Handle Header */}
                        <div
                            data-drag-handle
                            className="h-8 bg-gray-900/80 border-b border-cyan-500/20 flex items-center justify-between px-3 cursor-grab active:cursor-grabbing shrink-0"
                        >
                            <span className="text-xs font-bold tracking-widest text-cyan-500/70">CAD PROTOTYPE</span>
                            <button
                                onClick={() => setShowCadWindow(false)}
                                className="text-gray-400 hover:text-red-400 hover:bg-red-500/20 p-1 rounded transition-colors"
                            >
                                ✕
                            </button>
                        </div>
                        <div className="absolute inset-0 bg-[url('/noise.svg')] opacity-10 pointer-events-none mix-blend-overlay z-10"></div>
                        <div className="relative z-20 flex-1 min-h-0">
                            <CadWindow
                                data={cadData}
                                thoughts={cadThoughts}
                                retryInfo={cadRetryInfo}
                                onClose={() => setShowCadWindow(false)}
                                socket={socket}
                            />
                        </div>
                    </div>
                )}


                {/* Browser Window Overlay */}
                {showBrowserWindow && (
                    <div
                        id="browser"
                        className={`absolute flex flex-col transition-all duration-200 
                        backdrop-blur-xl bg-black/40 border border-white/10 shadow-2xl overflow-hidden rounded-lg
                        ${activeDragElement === 'browser' ? 'ring-2 ring-green-500 bg-green-500/10' : ''}
                    `}
                        style={{
                            left: elementPositions.browser?.x || window.innerWidth / 2 - 200,
                            top: elementPositions.browser?.y || window.innerHeight / 2,
                            transform: 'translate(-50%, -50%)',
                            width: `${elementSizes.browser.w}px`,
                            height: `${elementSizes.browser.h}px`,
                            pointerEvents: 'auto',
                            zIndex: getZIndex('browser')
                        }}
                        onMouseDown={(e) => handleMouseDown(e, 'browser')}
                    >
                        <div className="absolute inset-0 bg-[url('/noise.svg')] opacity-10 pointer-events-none mix-blend-overlay z-10"></div>
                        <div className="relative z-20 w-full h-full">
                            <BrowserWindow
                                imageSrc={browserData.image}
                                logs={browserData.logs}
                                onClose={() => setShowBrowserWindow(false)}
                                socket={socket}
                            />
                        </div>
                    </div>
                )}


                {/* Chat Module */}
                <ChatModule
                    messages={messages}
                    inputValue={inputValue}
                    setInputValue={setInputValue}
                    handleSend={handleSend}
                    isModularMode={isModularMode}
                    activeDragElement={activeDragElement}
                    position={elementPositions.chat}
                    width={elementSizes.chat.w}
                    height={elementSizes.chat.h}
                    onMouseDown={(e) => handleMouseDown(e, 'chat')}
                />

                {/* Footer Controls / Tools Module */}
                <div className="z-20 flex justify-center pb-10 pointer-events-none">
                    <ToolsModule
                        isConnected={isConnected}
                        isMuted={isMuted}
                        isVideoOn={isVideoOn}
                        isHandTrackingEnabled={isHandTrackingEnabled}
                        showSettings={showSettings}
                        onTogglePower={togglePower}
                        onToggleMute={toggleMute}
                        onToggleVideo={toggleVideo}
                        onToggleSettings={() => setShowSettings(!showSettings)}
                        onToggleHand={() => setIsHandTrackingEnabled(!isHandTrackingEnabled)}
                        onToggleKasa={toggleKasaWindow}
                        showKasaWindow={showKasaWindow}
                        onTogglePrinter={togglePrinterWindow}
                        showPrinterWindow={showPrinterWindow}
                        onToggleCad={() => setShowCadWindow(!showCadWindow)}
                        showCadWindow={showCadWindow}
                        onToggleBrowser={() => setShowBrowserWindow(!showBrowserWindow)}
                        showBrowserWindow={showBrowserWindow}
                        activeDragElement={activeDragElement}
                        position={elementPositions.tools}
                        onMouseDown={(e) => handleMouseDown(e, 'tools')}
                    />
                </div>

                {/* Kasa Window */}
                {showKasaWindow && (
                    <KasaWindow
                        socket={socket}
                        position={elementPositions.kasa}
                        activeDragElement={activeDragElement}
                        setActiveDragElement={setActiveDragElement}
                        devices={kasaDevices}
                        onClose={() => setShowKasaWindow(false)}
                        onMouseDown={(e) => handleMouseDown(e, 'kasa')}
                        zIndex={getZIndex('kasa')}
                    />
                )}

                {/* Printer Window */}
                {showPrinterWindow && (
                    <PrinterWindow
                        socket={socket}
                        onClose={() => setShowPrinterWindow(false)}
                        position={elementPositions.printer}
                        onMouseDown={(e) => handleMouseDown(e, 'printer')}
                        activeDragElement={activeDragElement}
                        setActiveDragElement={setActiveDragElement}
                        zIndex={getZIndex('printer')}
                    />
                )}

                {/* Memory Prompt removed - memory is now actively saved to project */}

                {/* Tool Confirmation Modal */}
                <ConfirmationPopup
                    request={confirmationRequest}
                    onConfirm={handleConfirmTool}
                    onDeny={handleDenyTool}
                />
            </div>

            {/* Face Authentication Lock Screen */}
            {isLockScreenVisible && !isAuthenticated && (
                <AuthLock
                    socket={socket}
                    onAuthenticated={(val) => {
                        setIsAuthenticated(val);
                    }}
                    onAnimationComplete={() => {
                        setIsLockScreenVisible(false);
                    }}
                />
            )}
        </div>
    );
}

export default App;
