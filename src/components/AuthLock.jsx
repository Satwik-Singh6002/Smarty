import React, { useEffect, useState } from 'react';
import { Lock, Unlock, User, Power } from 'lucide-react';

const AuthLock = ({ socket, onAuthenticated, onAnimationComplete }) => {
    const [frameSrc, setFrameSrc] = useState(null);
    const [message, setMessage] = useState("Initializing Security...");
    const [isUnlocking, setIsUnlocking] = useState(false);
    
    // Registration State
    const [needsRegistration, setNeedsRegistration] = useState(false);
    const [isRegistering, setIsRegistering] = useState(false);

    useEffect(() => {
        if (!socket) {
            console.warn("[AuthLock] No socket object provided.");
            return;
        }

        console.log("[AuthLock] Mounted. Socket connected status:", socket.connected);

        const handleAuthStatus = (data) => {
            console.log("[AuthLock] Received auth_status:", data);
            if (data.authenticated && !isUnlocking) {
                // Start Unlock Sequence
                setIsUnlocking(true);
                setMessage("Identity Verified. Access Granted.");

                // Wait for animation then notify parent
                setTimeout(() => {
                    onAuthenticated(true);
                }, 2000); // 2 seconds animation
            } else if (!data.authenticated && !isUnlocking) {
                if (data.needs_registration) {
                    setNeedsRegistration(true);
                    setIsRegistering(false);
                    setMessage("No face registered. Please register owner's face.");
                } else if (data.is_registering) {
                    setNeedsRegistration(true);
                    setIsRegistering(true);
                    setMessage("Position face and click Capture.");
                } else {
                    setNeedsRegistration(false);
                    setIsRegistering(false);
                    setMessage("Look at the camera to unlock.");
                }
            }
        };

        const handleAuthFrame = (data) => {
            setFrameSrc(`data:image/jpeg;base64,${data.image}`);
        };

        const handleRegistrationSuccess = (data) => {
            console.log("[AuthLock] Received registration_success:", data);
            setMessage("Face registered successfully!");
            setNeedsRegistration(false);
            setIsRegistering(false);
        };

        const handleError = (data) => {
            console.error("[AuthLock] Received error:", data);
            if (data.msg) {
                setMessage(data.msg);
            }
        };

        socket.on('auth_status', handleAuthStatus);
        socket.on('auth_frame', handleAuthFrame);
        socket.on('registration_success', handleRegistrationSuccess);
        socket.on('error', handleError);

        // Check registration on load
        console.log("[AuthLock] Emitting check_registration...");
        socket.emit('check_registration');

        return () => {
            console.log("[AuthLock] Unmounting / cleaning up listeners.");
            socket.off('auth_status', handleAuthStatus);
            socket.off('auth_frame', handleAuthFrame);
            socket.off('registration_success', handleRegistrationSuccess);
            socket.off('error', handleError);
        };
    }, [socket, onAuthenticated, onAnimationComplete, isUnlocking]);

    const handleExit = () => {
        console.log("[AuthLock] Exit requested");
        try {
            const { ipcRenderer } = window.require('electron');
            ipcRenderer.send('window-close');
        } catch (err) {
            console.log("Not running in Electron, closing window...");
            window.close();
        }
    };

    const themeColor = isUnlocking ? 'text-green-500' : 'text-cyan-500';
    const borderColor = isUnlocking ? 'border-green-500' : 'border-cyan-500';
    const shadowColor = isUnlocking ? 'shadow-[0_0_50px_rgba(34,197,94,0.4)]' : 'shadow-[0_0_50px_rgba(34,211,238,0.2)]';
    const bgGradient = isUnlocking
        ? 'from-green-900/40 via-black to-black'
        : 'from-cyan-900/20 via-black to-black';

    return (
        <div className={`fixed inset-0 z-[9999] bg-black flex flex-col items-center justify-center font-mono select-none transition-all duration-[2000ms] ${isUnlocking ? 'opacity-0 scale-110 pointer-events-none' : 'opacity-100'}`}
            style={{ transitionDelay: '2000ms' }}> {/* Delay fade out to show success state */}

            {/* Background Grid */}
            <div className={`absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] ${bgGradient} pointer-events-none transition-colors duration-[1500ms]`}></div>

            {/* Top Bar Actions / Exit Button */}
            {!isUnlocking && (
                <button
                    onClick={handleExit}
                    className="absolute top-6 right-6 p-2 border border-red-500/30 rounded bg-red-950/20 text-red-400 hover:bg-red-500/30 transition-all flex items-center justify-center gap-1.5 text-xs font-mono tracking-wider z-50 cursor-pointer active:scale-95"
                    title="Exit Application"
                >
                    <Power size={14} />
                    Exit
                </button>
            )}

            <div className={`relative flex flex-col items-center gap-6 p-10 border ${borderColor}/30 rounded-lg bg-black/80 backdrop-blur-xl ${shadowColor} transition-all duration-[1500ms]`}>
                <div className={`text-3xl font-bold tracking-[0.3em] uppercase drop-shadow-[0_0_10px_currentColor] flex items-center gap-4 ${themeColor} transition-colors duration-1000`}>
                    {isUnlocking ? <Unlock size={32} /> : <Lock size={32} />}
                    {isUnlocking ? "SYSTEM UNLOCKED" : (needsRegistration ? "ENROLL OWNER" : "SYSTEM LOCKED")}
                </div>

                {/* Camera Feed Frame */}
                <div className={`relative w-64 h-64 border-2 ${borderColor}/50 rounded-lg overflow-hidden bg-gray-900 shadow-inner flex items-center justify-center transition-colors duration-500`}>
                    {needsRegistration && !isRegistering ? (
                        <div className="p-4 text-[11px] text-center text-cyan-300/80 leading-relaxed font-sans animate-fade-in">
                            <User size={36} className="mx-auto mb-3 text-cyan-500/60 animate-bounce" />
                            A.D.A requires a registered owner's face for biometric security.<br/><br/>
                            Biometric data is processed locally and never uploaded.
                        </div>
                    ) : frameSrc ? (
                        <img
                            src={frameSrc}
                            alt="Auth Camera"
                            className={`w-full h-full object-cover transform scale-x-[-1] transition-opacity duration-500 ${isUnlocking ? 'opacity-50 grayscale' : 'opacity-100'}`}
                        />
                    ) : (
                        <div className={`animate-pulse ${isUnlocking ? 'text-green-800' : 'text-cyan-800'}`}>
                            <User size={64} />
                        </div>
                    )}

                    {/* Scanning Line Animation - remove on unlock/idle registration */}
                    {!isUnlocking && (!needsRegistration || isRegistering) && (
                        <div className="absolute top-0 left-0 w-full h-1 bg-cyan-400/80 shadow-[0_0_15px_cyan] animate-[scan_2s_ease-in-out_infinite]"></div>
                    )}

                    {/* Success Overlay */}
                    {isUnlocking && (
                        <div className="absolute inset-0 flex items-center justify-center bg-green-500/20 animate-pulse">
                            <Unlock size={64} className="text-green-400 drop-shadow-[0_0_20px_rgba(74,222,128,0.8)]" />
                        </div>
                    )}
                </div>

                <div className={`text-sm tracking-widest text-center max-w-xs ${isUnlocking ? 'text-green-300' : 'text-cyan-300'} animate-pulse transition-colors duration-500`}>
                    {message}
                </div>

                {/* Registration Buttons */}
                {needsRegistration && (
                    <div className="mt-2 w-full flex justify-center">
                        {!isRegistering ? (
                            <button
                                onClick={() => {
                                    console.log("[AuthLock] Emitting start_registration...");
                                    socket.emit('start_registration');
                                }}
                                className="px-4 py-2 border border-cyan-500/50 rounded bg-cyan-950/40 text-cyan-400 font-mono text-xs uppercase tracking-widest hover:bg-cyan-500/20 transition-all shadow-[0_0_15px_rgba(6,182,212,0.1)] active:scale-95"
                            >
                                Start Face Registration
                            </button>
                        ) : (
                            <button
                                onClick={() => {
                                    console.log("[AuthLock] Emitting capture_registration...");
                                    socket.emit('capture_registration');
                                }}
                                className="px-4 py-2 border border-green-500/50 rounded bg-green-950/40 text-green-400 font-mono text-xs uppercase tracking-widest hover:bg-green-500/20 transition-all shadow-[0_0_15px_rgba(34,197,94,0.1)] active:scale-95 animate-pulse"
                            >
                                Capture & Register Face
                            </button>
                        )}
                    </div>
                )}
            </div>

            {/* Keyframe for scan animation */}
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

export default AuthLock;
