import React, { useEffect, useState, useRef } from 'react';
import { Lock, Unlock, User, Power, Camera, RefreshCw, CheckCircle2, ShieldCheck, AlertCircle, Scan, Sparkles } from 'lucide-react';

const AuthLock = ({ socket, onAuthenticated, onAnimationComplete }) => {
    const [frameSrc, setFrameSrc] = useState(null);
    const [faceDetected, setFaceDetected] = useState(false);
    const [faceCentered, setFaceCentered] = useState(false);
    const [faceDistanceOk, setFaceDistanceOk] = useState(false);
    const [qualityMsg, setQualityMsg] = useState("Looking for face...");
    const [similarity, setSimilarity] = useState(0.0);
    const [statusMessage, setStatusMessage] = useState("Initializing Biometric Scanner...");
    const [isUnlocking, setIsUnlocking] = useState(false);
    
    // Enrollment state
    const [needsRegistration, setNeedsRegistration] = useState(false);
    const [isRegistering, setIsRegistering] = useState(false);
    const [enrollProgress, setEnrollProgress] = useState(0);
    const [isEnrolling, setIsEnrolling] = useState(false);
    const [registrationSuccess, setRegistrationSuccess] = useState(false);

    // Keep callback refs stable to prevent unneeded re-subscriptions
    const onAuthRef = useRef(onAuthenticated);
    const onCompleteRef = useRef(onAnimationComplete);
    const isUnlockingRef = useRef(false);

    useEffect(() => {
        onAuthRef.current = onAuthenticated;
        onCompleteRef.current = onAnimationComplete;
    }, [onAuthenticated, onAnimationComplete]);

    useEffect(() => {
        if (!socket) {
            console.warn("[AuthLock] No socket object provided.");
            return;
        }

        console.log("[AuthLock] Mounting biometric security interface...");

        const handleAuthStatus = (data) => {
            console.log("[AuthLock] auth_status:", data);
            
            if (data.authenticated && !isUnlockingRef.current) {
                isUnlockingRef.current = true;
                setIsUnlocking(true);
                setStatusMessage("Identity Verified. Access Granted.");

                setTimeout(() => {
                    if (onAuthRef.current) onAuthRef.current(true);
                    if (onCompleteRef.current) onCompleteRef.current();
                }, 1200);
            } else if (!data.authenticated && !isUnlockingRef.current) {
                if (data.needs_registration) {
                    setNeedsRegistration(true);
                    setIsRegistering(true);
                    setStatusMessage("No owner face registered. Please enroll face.");
                } else if (data.is_registering) {
                    setNeedsRegistration(true);
                    setIsRegistering(true);
                    setStatusMessage("Position face in the reticle and click Enroll.");
                } else {
                    setNeedsRegistration(false);
                    setIsRegistering(false);
                    setStatusMessage("Look into the camera to unlock.");
                }
            }
        };

        const handleAuthFrame = (data) => {
            if (!data) return;
            if (typeof data === 'object') {
                if (data.image) setFrameSrc(`data:image/jpeg;base64,${data.image}`);
                if (typeof data.face_detected !== 'undefined') setFaceDetected(Boolean(data.face_detected));
                if (typeof data.face_centered !== 'undefined') setFaceCentered(Boolean(data.face_centered));
                if (typeof data.face_distance_ok !== 'undefined') setFaceDistanceOk(Boolean(data.face_distance_ok));
                if (data.quality_msg) setQualityMsg(data.quality_msg);
                if (typeof data.similarity === 'number') setSimilarity(data.similarity);
                if (typeof data.enrollment_progress === 'number' && data.enrollment_progress > 0) {
                    setEnrollProgress(data.enrollment_progress);
                }
            } else {
                setFrameSrc(`data:image/jpeg;base64,${data}`);
            }
        };

        const handleEnrollProgress = (data) => {
            console.log("[AuthLock] enroll_progress:", data);
            setIsEnrolling(true);
            if (typeof data.progress === 'number') {
                setEnrollProgress(data.progress);
            }
            if (data.message) {
                setStatusMessage(data.message);
            }
        };

        const handleRegistrationSuccess = (data) => {
            console.log("[AuthLock] registration_success:", data);
            setRegistrationSuccess(true);
            setEnrollProgress(100);
            setIsEnrolling(false);
            setStatusMessage("Owner Face Enrolled Successfully!");
            
            setTimeout(() => {
                isUnlockingRef.current = true;
                setIsUnlocking(true);
                setTimeout(() => {
                    if (onAuthRef.current) onAuthRef.current(true);
                    if (onCompleteRef.current) onCompleteRef.current();
                }, 1200);
            }, 800);
        };

        const handleError = (data) => {
            console.error("[AuthLock] Error received:", data);
            setIsEnrolling(false);
            if (data && data.msg) {
                setStatusMessage(data.msg);
            }
        };

        socket.on('auth_status', handleAuthStatus);
        socket.on('auth_frame', handleAuthFrame);
        socket.on('enroll_progress', handleEnrollProgress);
        socket.on('registration_success', handleRegistrationSuccess);
        socket.on('error', handleError);

        // Single check on mount
        socket.emit('check_registration');

        return () => {
            console.log("[AuthLock] Unmounting and cleaning listeners.");
            socket.off('auth_status', handleAuthStatus);
            socket.off('auth_frame', handleAuthFrame);
            socket.off('enroll_progress', handleEnrollProgress);
            socket.off('registration_success', handleRegistrationSuccess);
            socket.off('error', handleError);
        };
    }, [socket]);

    const handleStartMultiEnrollment = () => {
        setIsEnrolling(true);
        setEnrollProgress(10);
        setStatusMessage("Hold steady — calibrating multi-sample profile...");
        if (socket) {
            socket.emit('start_enrollment');
        }
    };

    const handleSingleCapture = () => {
        setStatusMessage("Processing biometric capture...");
        if (socket) {
            socket.emit('capture_registration');
        }
    };

    const handleStartRegistrationMode = () => {
        setNeedsRegistration(true);
        setIsRegistering(true);
        setEnrollProgress(0);
        setStatusMessage("Position face in the reticle and click Enroll.");
        if (socket) {
            socket.emit('start_registration');
        }
    };

    const handleSwitchToAuth = () => {
        setNeedsRegistration(false);
        setIsRegistering(false);
        setIsEnrolling(false);
        setEnrollProgress(0);
        setStatusMessage("Looking for owner face...");
        if (socket) {
            socket.emit('check_registration');
        }
    };

    const handleExit = () => {
        const electronAPI = window.electronAPI;
        if (electronAPI && typeof electronAPI.close === 'function') {
            electronAPI.close();
        } else {
            window.close();
        }
    };

    const isSuccess = isUnlocking || registrationSuccess;
    const isReadyToEnroll = faceDetected && faceCentered && faceDistanceOk;

    const themeColor = isSuccess ? 'text-emerald-400' : 'text-cyan-400';
    const borderColor = isSuccess 
        ? 'border-emerald-500' 
        : (isReadyToEnroll ? 'border-emerald-400/90' : (faceDetected ? 'border-cyan-400' : 'border-cyan-800/60'));
    
    const shadowColor = isSuccess 
        ? 'shadow-[0_0_70px_rgba(16,185,129,0.35)]' 
        : (isReadyToEnroll ? 'shadow-[0_0_50px_rgba(52,211,153,0.25)]' : 'shadow-[0_0_40px_rgba(6,182,212,0.15)]');

    const bgGradient = isSuccess
        ? 'from-emerald-950/40 via-black to-black'
        : 'from-cyan-950/30 via-black to-black';

    const matchPercent = Math.min(100, Math.max(0, Math.round(similarity * 100)));

    return (
        <div 
            className={`fixed inset-0 z-[9999] bg-black/95 flex flex-col items-center justify-center font-mono select-none transition-all duration-1000 ${
                isUnlocking ? 'opacity-0 scale-105 pointer-events-none' : 'opacity-100 scale-100'
            }`}
        >
            {/* Ambient Cyber Background */}
            <div className={`absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] ${bgGradient} pointer-events-none transition-colors duration-1000`}></div>
            <div className="absolute inset-0 bg-[url('/noise.svg')] opacity-5 pointer-events-none"></div>

            {/* Top Right Exit Application Button */}
            {!isUnlocking && (
                <button
                    onClick={handleExit}
                    className="absolute top-6 right-6 px-3 py-1.5 border border-red-500/40 rounded bg-red-950/20 text-red-400 hover:bg-red-500/30 hover:border-red-500/80 transition-all flex items-center justify-center gap-2 text-xs font-mono tracking-wider z-50 cursor-pointer active:scale-95"
                    title="Exit Application"
                >
                    <Power size={13} />
                    EXIT
                </button>
            )}

            {/* Central Security Card Frame */}
            <div className={`relative flex flex-col items-center gap-5 p-8 sm:p-10 border ${borderColor} rounded-2xl bg-black/85 backdrop-blur-2xl ${shadowColor} transition-all duration-700 max-w-md w-full mx-4`}>
                
                {/* Cyber Brackets */}
                <div className={`absolute -top-1.5 -left-1.5 w-4 h-4 border-t-2 border-l-2 ${borderColor}`}></div>
                <div className={`absolute -top-1.5 -right-1.5 w-4 h-4 border-t-2 border-r-2 ${borderColor}`}></div>
                <div className={`absolute -bottom-1.5 -left-1.5 w-4 h-4 border-b-2 border-l-2 ${borderColor}`}></div>
                <div className={`absolute -bottom-1.5 -right-1.5 w-4 h-4 border-b-2 border-r-2 ${borderColor}`}></div>

                {/* Header Title with Lock Status */}
                <div className="flex flex-col items-center gap-1.5">
                    <div className={`text-2xl sm:text-3xl font-extrabold tracking-[0.25em] uppercase drop-shadow-[0_0_12px_currentColor] flex items-center gap-3 ${themeColor} transition-colors duration-500`}>
                        {isSuccess ? (
                            <Unlock size={28} className="animate-pulse" />
                        ) : (
                            <Lock size={28} />
                        )}
                        <span>
                            {isSuccess 
                                ? "ACCESS GRANTED" 
                                : (isRegistering ? "BIOMETRIC ENROLL" : "SYSTEM LOCKED")}
                        </span>
                    </div>
                    <div className="text-[10px] uppercase tracking-widest text-cyan-500/70 flex items-center gap-1.5">
                        <ShieldCheck size={12} className="text-cyan-400" />
                        {isRegistering ? "High-Accuracy Multi-Sample Enrollment" : "Biometric Face Recognition"}
                    </div>
                </div>

                {/* Camera Viewport with Circular Scanner Ring */}
                <div className={`relative w-64 h-64 border-2 ${borderColor} rounded-2xl overflow-hidden bg-gray-950 shadow-inner flex items-center justify-center transition-colors duration-500`}>
                    
                    {frameSrc ? (
                        <img
                            src={frameSrc}
                            alt="Biometric Feed"
                            className={`w-full h-full object-cover transform scale-x-[-1] transition-all duration-500 ${
                                isSuccess ? 'brightness-110 saturate-125' : 'brightness-100'
                            }`}
                        />
                    ) : (
                        <div className={`flex flex-col items-center gap-3 animate-pulse ${isSuccess ? 'text-emerald-500' : 'text-cyan-600'}`}>
                            <User size={64} />
                            <span className="text-xs tracking-wider opacity-70">Initializing Camera Sensor...</span>
                        </div>
                    )}

                    {/* Biometric Reticle & Target Rings */}
                    <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                        {/* Target Circle */}
                        <div className={`w-44 h-44 rounded-full border-2 transition-all duration-500 ${
                            isSuccess 
                                ? 'border-emerald-400 scale-95 shadow-[0_0_25px_rgba(16,185,129,0.7)]' 
                                : (isReadyToEnroll 
                                    ? 'border-emerald-400/90 scale-100 shadow-[0_0_20px_rgba(52,211,153,0.5)] animate-pulse' 
                                    : (faceDetected 
                                        ? 'border-cyan-400/70 border-dashed scale-100' 
                                        : 'border-cyan-500/30 border-dashed scale-105'))
                        }`}></div>

                        {/* Scanner Laser Sweep (Active when scanning) */}
                        {!isSuccess && frameSrc && !isEnrolling && (
                            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_12px_cyan] animate-[scan_2.2s_ease-in-out_infinite]"></div>
                        )}

                        {/* Success Hologram Badge */}
                        {isSuccess && (
                            <div className="absolute inset-0 flex flex-col items-center justify-center bg-emerald-950/45 backdrop-blur-[2px] transition-all animate-fade-in">
                                <CheckCircle2 size={64} className="text-emerald-400 drop-shadow-[0_0_30px_rgba(16,185,129,0.95)] animate-bounce" />
                                <span className="mt-2 text-xs font-bold text-emerald-300 tracking-widest uppercase">Verified</span>
                            </div>
                        )}
                    </div>

                    {/* Top Status Pill: Face Alignment Indicator */}
                    {frameSrc && !isSuccess && (
                        <div className="absolute top-2 left-2 z-20">
                            <span className={`px-2 py-0.5 rounded text-[9px] font-bold tracking-wider uppercase backdrop-blur-md flex items-center gap-1 border ${
                                isReadyToEnroll
                                    ? 'bg-emerald-950/90 text-emerald-300 border-emerald-500/70 shadow-[0_0_10px_rgba(16,185,129,0.4)]'
                                    : (faceDetected 
                                        ? 'bg-cyan-950/80 text-cyan-300 border-cyan-500/50' 
                                        : 'bg-black/75 text-cyan-400/60 border-cyan-800/40')
                            }`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${isReadyToEnroll ? 'bg-emerald-400 animate-ping' : (faceDetected ? 'bg-cyan-400' : 'bg-cyan-700')}`}></span>
                                {isReadyToEnroll ? "READY TO ENROLL" : (faceDetected ? "FACE DETECTED" : "SEARCHING")}
                            </span>
                        </div>
                    )}

                    {/* Live Match Score Gauge (in auth mode) */}
                    {!isRegistering && !isSuccess && frameSrc && faceDetected && similarity > 0 && (
                        <div className="absolute bottom-2 left-2 right-2 z-20 bg-black/85 backdrop-blur-md px-2.5 py-1.5 rounded-lg border border-cyan-800/60 flex items-center justify-between">
                            <span className="text-[10px] text-cyan-400 uppercase tracking-wider flex items-center gap-1">
                                <Scan size={11} />
                                Match Confidence
                            </span>
                            <span className={`text-[10px] font-bold ${similarity >= 0.93 ? 'text-emerald-400' : 'text-cyan-300'}`}>
                                {matchPercent}%
                            </span>
                        </div>
                    )}
                </div>

                {/* Progressive Enrollment Progress Bar */}
                {isRegistering && (enrollProgress > 0 || isEnrolling) && (
                    <div className="w-full flex flex-col gap-1.5">
                        <div className="flex justify-between items-center text-[10px] font-mono tracking-wider">
                            <span className="text-cyan-400 uppercase">Calibrating 5-Sample Profile</span>
                            <span className="text-emerald-400 font-bold">{enrollProgress}%</span>
                        </div>
                        <div className="w-full h-2 bg-gray-900 rounded-full overflow-hidden border border-cyan-800/50">
                            <div 
                                className="h-full bg-gradient-to-r from-cyan-500 via-teal-400 to-emerald-400 transition-all duration-300 shadow-[0_0_12px_rgba(52,211,153,0.5)]"
                                style={{ width: `${enrollProgress}%` }}
                            />
                        </div>
                    </div>
                )}

                {/* Real-time Guidance Message */}
                <div className={`text-xs sm:text-sm tracking-wider text-center max-w-xs font-medium transition-colors duration-300 ${
                    isSuccess 
                        ? 'text-emerald-300' 
                        : (isReadyToEnroll ? 'text-emerald-300 font-bold' : (faceDetected ? 'text-cyan-300' : 'text-cyan-400/80'))
                }`}>
                    {isRegistering && !isSuccess && qualityMsg ? qualityMsg : statusMessage}
                </div>

                {/* Primary Action Controls */}
                <div className="w-full flex flex-col gap-2.5 mt-1">
                    {/* Enrollment Controls */}
                    {isRegistering ? (
                        <div className="flex flex-col gap-2 w-full">
                            {/* Main Recommended Multi-Sample Enrollment Button */}
                            <button
                                onClick={handleStartMultiEnrollment}
                                disabled={isEnrolling}
                                className={`w-full py-2.5 px-4 rounded-lg font-mono text-xs uppercase tracking-widest font-bold flex items-center justify-center gap-2 transition-all cursor-pointer border ${
                                    isReadyToEnroll
                                        ? 'bg-emerald-500/25 text-emerald-300 border-emerald-500/70 hover:bg-emerald-500/35 shadow-[0_0_20px_rgba(16,185,129,0.35)] animate-pulse'
                                        : 'bg-cyan-950/40 text-cyan-400 border-cyan-700/50 hover:bg-cyan-900/40'
                                } active:scale-98`}
                            >
                                <Sparkles size={15} />
                                {isEnrolling ? `Enrolling (${enrollProgress}%)...` : "Start Multi-Sample Enrollment"}
                            </button>

                            {/* Secondary Quick Capture Button */}
                            <button
                                onClick={handleSingleCapture}
                                disabled={isEnrolling}
                                className="w-full py-1.5 px-3 rounded border border-cyan-800/50 bg-black/40 hover:bg-cyan-950/30 text-cyan-400/90 hover:text-cyan-200 text-[11px] font-mono tracking-wider flex items-center justify-center gap-1.5 transition-all active:scale-98"
                            >
                                <Camera size={13} />
                                Instant Single Capture
                            </button>

                            {/* Return to Unlock if face was already enrolled */}
                            {!needsRegistration && (
                                <button
                                    onClick={handleSwitchToAuth}
                                    className="text-[11px] text-cyan-500/70 hover:text-cyan-300 text-center py-1 transition-colors"
                                >
                                    Cancel & Return to Unlock
                                </button>
                            )}
                        </div>
                    ) : (
                        /* In Locked Authentication Mode */
                        <div className="flex flex-col items-center gap-2 w-full">
                            <button
                                onClick={handleStartRegistrationMode}
                                className="w-full py-2 px-3 rounded border border-cyan-800/60 bg-cyan-950/20 hover:bg-cyan-900/30 text-cyan-400 hover:text-cyan-200 text-xs font-mono tracking-wider flex items-center justify-center gap-2 transition-all active:scale-98"
                            >
                                <RefreshCw size={13} />
                                Re-enroll Owner Face
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* CSS Keyframe for Laser Scanning Animation */}
            <style>{`
                @keyframes scan {
                    0% { top: 0%; opacity: 0.2; }
                    50% { top: 96%; opacity: 1; }
                    100% { top: 0%; opacity: 0.2; }
                }
            `}</style>
        </div>
    );
};

export default React.memo(AuthLock);
