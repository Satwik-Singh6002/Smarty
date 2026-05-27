import React, { useState, useEffect } from 'react';
import { X, ShieldCheck, UserCircle, Trash2, UserPlus, Camera } from 'lucide-react';

const TOOLS = [
    { id: 'generate_cad', label: 'Generate CAD' },
    { id: 'run_web_agent', label: 'Web Agent' },
    { id: 'create_directory', label: 'Create Folder' },
    { id: 'write_file', label: 'Write File' },
    { id: 'read_directory', label: 'Read Directory' },
    { id: 'read_file', label: 'Read File' },
    { id: 'create_project', label: 'Create Project' },
    { id: 'switch_project', label: 'Switch Project' },
    { id: 'list_projects', label: 'List Projects' },
    { id: 'list_smart_devices', label: 'List Devices' },
    { id: 'control_light', label: 'Control Light' },
    { id: 'discover_printers', label: 'Discover Printers' },
    { id: 'print_stl', label: 'Print 3D Model' },
    { id: 'iterate_cad', label: 'Iterate CAD' },
];

const SettingsWindow = ({
    socket,
    micDevices,
    speakerDevices,
    webcamDevices,
    selectedMicId,
    setSelectedMicId,
    selectedSpeakerId,
    setSelectedSpeakerId,
    selectedWebcamId,
    setSelectedWebcamId,
    cursorSensitivity,
    setCursorSensitivity,
    faceAuthEnabled,
    isFaceRegistered,
    onClose
}) => {
    const [permissions, setPermissions] = useState({});
    const [showRegisterCamera, setShowRegisterCamera] = useState(false);
    const [registerFrameSrc, setRegisterFrameSrc] = useState(null);
    const [registerMessage, setRegisterMessage] = useState('');
    const [isCapturing, setIsCapturing] = useState(false);
    const [showClearConfirm, setShowClearConfirm] = useState(false);

    useEffect(() => {
        socket.emit('get_settings');

        const handleSettings = (settings) => {
            if (settings && settings.tool_permissions) {
                setPermissions(settings.tool_permissions);
            }
        };

        const handleAuthFrame = (data) => {
            if (showRegisterCamera || isCapturing) {
                setRegisterFrameSrc(`data:image/jpeg;base64,${data.image}`);
            }
        };

        const handleRegistrationSuccess = (data) => {
            setRegisterMessage('Face registered successfully!');
            setIsCapturing(false);
            setTimeout(() => {
                setShowRegisterCamera(false);
                setRegisterFrameSrc(null);
                setRegisterMessage('');
            }, 1500);
        };

        const handleError = (data) => {
            if (data.msg && showRegisterCamera) {
                setRegisterMessage(data.msg);
                setIsCapturing(false);
            }
        };

        socket.on('settings', handleSettings);
        socket.on('auth_frame', handleAuthFrame);
        socket.on('registration_success', handleRegistrationSuccess);
        socket.on('error', handleError);

        return () => {
            socket.off('settings', handleSettings);
            socket.off('auth_frame', handleAuthFrame);
            socket.off('registration_success', handleRegistrationSuccess);
            socket.off('error', handleError);
        };
    }, [socket, showRegisterCamera, isCapturing]);

    const togglePermission = (toolId) => {
        const currentVal = permissions[toolId] !== false;
        const nextVal = !currentVal;
        socket.emit('update_settings', { tool_permissions: { [toolId]: nextVal } });
    };

    const toggleFaceAuth = () => {
        const newVal = !faceAuthEnabled;
        if (newVal && !isFaceRegistered) {
            setRegisterMessage('Register a face first before enabling Face Lock.');
            setTimeout(() => setRegisterMessage(''), 3000);
            return;
        }
        socket.emit('update_settings', { face_auth_enabled: newVal });
    };

    const handleAddFace = () => {
        if (isFaceRegistered) {
            // Reset and re-register
            socket.emit('reset_registration');
        }
        setShowRegisterCamera(true);
        setRegisterMessage('Starting camera...');
        setIsCapturing(false);
        setTimeout(() => {
            socket.emit('start_registration');
            setIsCapturing(true);
            setRegisterMessage('Position your face and click Capture.');
        }, 300);
    };

    const handleCaptureFace = () => {
        setRegisterMessage('Capturing...');
        socket.emit('capture_registration');
    };

    const handleClearFace = () => {
        socket.emit('delete_registration');
        setShowClearConfirm(false);
        setShowRegisterCamera(false);
        setRegisterFrameSrc(null);
    };

    const handleCancelRegistration = () => {
        setShowRegisterCamera(false);
        setRegisterFrameSrc(null);
        setRegisterMessage('');
        setIsCapturing(false);
        // Stop the camera on the server
        if (socket) {
            socket.emit('reset_registration');
        }
    };

    return (
        <div className="absolute top-20 right-10 bg-black/90 border border-cyan-500/50 p-4 rounded-lg z-50 w-80 backdrop-blur-xl shadow-[0_0_30px_rgba(6,182,212,0.2)] max-h-[85vh] overflow-y-auto custom-scrollbar">
            <div className="flex justify-between items-center mb-4 border-b border-cyan-900/50 pb-2">
                <h2 className="text-cyan-400 font-bold text-sm uppercase tracking-wider">Settings</h2>
                <button onClick={onClose} className="text-cyan-600 hover:text-cyan-400">
                    <X size={16} />
                </button>
            </div>

            {/* ===== FACE AUTHENTICATION SECTION ===== */}
            <div className="mb-5">
                <div className="flex items-center gap-2 mb-3">
                    <ShieldCheck size={14} className="text-cyan-400" />
                    <h3 className="text-cyan-400 font-bold text-xs uppercase tracking-wider opacity-80">Face Authentication</h3>
                </div>

                {/* Face Lock Toggle */}
                <div className="flex items-center justify-between text-xs bg-gray-900/50 p-3 rounded-t border border-cyan-900/30">
                    <div className="flex items-center gap-2">
                        <span className="text-cyan-100/80">Face Lock</span>
                        {isFaceRegistered && (
                            <span className="text-[9px] text-green-400 bg-green-500/10 border border-green-500/30 px-1.5 py-0.5 rounded">Active</span>
                        )}
                    </div>
                    <button
                        onClick={toggleFaceAuth}
                        className={`relative w-8 h-4 rounded-full transition-colors duration-200 ${faceAuthEnabled ? 'bg-cyan-500/80' : 'bg-gray-700'}`}
                    >
                        <div
                            className={`absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform duration-200 ${faceAuthEnabled ? 'translate-x-4' : 'translate-x-0'}`}
                        />
                    </button>
                </div>

                {/* Face Data Section */}
                <div className="border border-t-0 border-cyan-900/30 rounded-b overflow-hidden">
                    <div className="px-3 py-2 bg-gray-900/30">
                        <span className="text-[10px] text-cyan-500/60 uppercase tracking-wider">Face data</span>
                    </div>

                    {/* Clear face data */}
                    {isFaceRegistered && (
                        <button
                            onClick={() => setShowClearConfirm(true)}
                            className="w-full text-left px-3 py-2.5 text-xs text-red-400 hover:bg-red-500/10 border-t border-cyan-900/20 transition-colors flex items-center gap-2"
                        >
                            <Trash2 size={12} />
                            Clear face data
                        </button>
                    )}

                    {/* Add / Replace face */}
                    <button
                        onClick={handleAddFace}
                        className="w-full text-left px-3 py-2.5 text-xs text-cyan-400 hover:bg-cyan-500/10 border-t border-cyan-900/20 transition-colors flex items-center gap-2"
                    >
                        <UserPlus size={12} />
                        {isFaceRegistered ? 'Add alternate face' : 'Add face data'}
                    </button>
                </div>

                {/* Clear Confirmation */}
                {showClearConfirm && (
                    <div className="mt-2 p-3 bg-red-950/30 border border-red-500/30 rounded text-xs">
                        <p className="text-red-300 mb-2">Remove all face data? Face Lock will be disabled.</p>
                        <div className="flex gap-2">
                            <button
                                onClick={handleClearFace}
                                className="px-3 py-1 bg-red-500/20 border border-red-500/40 rounded text-red-400 hover:bg-red-500/30 transition-colors"
                            >
                                Remove
                            </button>
                            <button
                                onClick={() => setShowClearConfirm(false)}
                                className="px-3 py-1 bg-gray-800 border border-gray-700 rounded text-gray-400 hover:bg-gray-700 transition-colors"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                )}

                {/* Registration Camera Modal */}
                {showRegisterCamera && (
                    <div className="mt-2 p-3 bg-gray-900/60 border border-cyan-500/30 rounded">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-[10px] text-cyan-400 uppercase tracking-wider font-bold">Face Registration</span>
                            <button onClick={handleCancelRegistration} className="text-gray-500 hover:text-red-400 transition-colors">
                                <X size={12} />
                            </button>
                        </div>

                        {/* Camera Feed */}
                        <div className="relative w-full aspect-square bg-black rounded border border-cyan-800/50 overflow-hidden mb-2">
                            {registerFrameSrc ? (
                                <img
                                    src={registerFrameSrc}
                                    alt="Registration Camera"
                                    className="w-full h-full object-cover transform scale-x-[-1]"
                                />
                            ) : (
                                <div className="w-full h-full flex items-center justify-center">
                                    <UserCircle size={48} className="text-cyan-800 animate-pulse" />
                                </div>
                            )}
                            {/* Scanning line */}
                            {registerFrameSrc && (
                                <div className="absolute top-0 left-0 w-full h-0.5 bg-cyan-400/80 shadow-[0_0_10px_cyan] animate-[scan_2s_ease-in-out_infinite]"></div>
                            )}
                        </div>

                        {/* Message */}
                        {registerMessage && (
                            <p className={`text-[10px] mb-2 text-center ${registerMessage.includes('success') ? 'text-green-400' : 'text-cyan-300/70'}`}>
                                {registerMessage}
                            </p>
                        )}

                        {/* Capture Button */}
                        {isCapturing && !registerMessage.includes('success') && (
                            <button
                                onClick={handleCaptureFace}
                                className="w-full py-2 bg-cyan-500/20 border border-cyan-500/40 rounded text-xs text-cyan-400 hover:bg-cyan-500/30 transition-all flex items-center justify-center gap-2 active:scale-95"
                            >
                                <Camera size={14} />
                                Capture Face
                            </button>
                        )}
                    </div>
                )}
            </div>

            {/* Microphone Section */}
            <div className="mb-4">
                <h3 className="text-cyan-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Microphone</h3>
                <select
                    value={selectedMicId}
                    onChange={(e) => setSelectedMicId(e.target.value)}
                    className="w-full bg-gray-900 border border-cyan-800 rounded p-2 text-xs text-cyan-100 focus:border-cyan-400 outline-none"
                >
                    {micDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Microphone ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            {/* Speaker Section */}
            <div className="mb-4">
                <h3 className="text-cyan-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Speaker</h3>
                <select
                    value={selectedSpeakerId}
                    onChange={(e) => setSelectedSpeakerId(e.target.value)}
                    className="w-full bg-gray-900 border border-cyan-800 rounded p-2 text-xs text-cyan-100 focus:border-cyan-400 outline-none"
                >
                    {speakerDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Speaker ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            {/* Webcam Section */}
            <div className="mb-6">
                <h3 className="text-cyan-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Webcam</h3>
                <select
                    value={selectedWebcamId}
                    onChange={(e) => setSelectedWebcamId(e.target.value)}
                    className="w-full bg-gray-900 border border-cyan-800 rounded p-2 text-xs text-cyan-100 focus:border-cyan-400 outline-none"
                >
                    {webcamDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Camera ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            {/* Cursor Section */}
            <div className="mb-6">
                <div className="flex justify-between mb-2">
                    <h3 className="text-cyan-400 font-bold text-xs uppercase tracking-wider opacity-80">Cursor Sensitivity</h3>
                    <span className="text-xs text-cyan-500">{cursorSensitivity}x</span>
                </div>
                <input
                    type="range"
                    min="1.0"
                    max="5.0"
                    step="0.1"
                    value={cursorSensitivity}
                    onChange={(e) => setCursorSensitivity(parseFloat(e.target.value))}
                    className="w-full accent-cyan-400 cursor-pointer h-1 bg-gray-800 rounded-lg appearance-none"
                />
            </div>

            {/* Tool Permissions Section */}
            <div className="mb-6">
                <h3 className="text-cyan-400 font-bold mb-3 text-xs uppercase tracking-wider opacity-80">Tool Confirmations</h3>
                <div className="space-y-2 max-h-40 overflow-y-auto pr-2 custom-scrollbar">
                    {TOOLS.map(tool => {
                        const isRequired = permissions[tool.id] !== false;
                        return (
                            <div key={tool.id} className="flex items-center justify-between text-xs bg-gray-900/50 p-2 rounded border border-cyan-900/30">
                                <span className="text-cyan-100/80">{tool.label}</span>
                                <button
                                    onClick={() => togglePermission(tool.id)}
                                    className={`relative w-8 h-4 rounded-full transition-colors duration-200 ${isRequired ? 'bg-cyan-500/80' : 'bg-gray-700'}`}
                                >
                                    <div
                                        className={`absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform duration-200 ${isRequired ? 'translate-x-4' : 'translate-x-0'}`}
                                    />
                                </button>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Scan animation keyframe */}
            <style>{`
                @keyframes scan {
                    0%, 100% { top: 0%; opacity: 0; }
                    50% { opacity: 1; }
                    100% { top: 100%; opacity: 0; }
                }
            `}</style>
        </div>
    );
};

export default SettingsWindow;
