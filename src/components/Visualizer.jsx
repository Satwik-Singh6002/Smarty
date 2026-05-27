import React, { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';

const Visualizer = ({ audioData, isListening, intensity = 0, width = 600, height = 400, overloadActive = false }) => {
    const canvasRef = useRef(null);

    // Use a ref for variables to avoid re-creating the animation loop on every frame
    const audioDataRef = useRef(audioData);
    const intensityRef = useRef(intensity);
    const isListeningRef = useRef(isListening);
    const overloadActiveRef = useRef(overloadActive);

    useEffect(() => {
        audioDataRef.current = audioData;
        intensityRef.current = intensity;
        isListeningRef.current = isListening;
        overloadActiveRef.current = overloadActive;
    }, [audioData, intensity, isListening, overloadActive]);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        // Ensure canvas internal resolution matches display size for sharpness
        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext('2d');
        let animationId;

        const draw = () => {
            const w = canvas.width;
            const h = canvas.height;
            const centerX = w / 2;
            const centerY = h / 2;

            const currentIntensity = intensityRef.current;
            const currentIsListening = isListeningRef.current;
            const currentAudioData = audioDataRef.current || [];
            const currentOverloadActive = overloadActiveRef.current;

            const baseRadius = Math.min(w, h) * 0.22;
            // Radius scales slightly with intensity for visual impact
            const radius = baseRadius + (currentIntensity * 25);

            ctx.clearRect(0, 0, w, h);

            // Draw glowing background radial gradient inside the circle
            const gradient = ctx.createRadialGradient(centerX, centerY, radius * 0.5, centerX, centerY, radius);
            if (currentOverloadActive) {
                gradient.addColorStop(0, 'rgba(239, 68, 68, 0.12)');
                gradient.addColorStop(0.8, 'rgba(249, 115, 22, 0.18)');
                gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
            } else {
                gradient.addColorStop(0, 'rgba(6, 182, 212, 0.05)');
                gradient.addColorStop(0.8, 'rgba(147, 51, 234, 0.08)');
                gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
            }
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
            ctx.fill();

            // Draw outer rotating dashed indicator rings (sci-fi HUD style)
            const rotationTime = Date.now() / (currentOverloadActive ? 800 : 3000);
            ctx.save();
            ctx.translate(centerX, centerY);
            ctx.rotate(rotationTime);
            ctx.beginPath();
            ctx.arc(0, 0, radius + 15, 0, Math.PI * 2);
            ctx.strokeStyle = currentOverloadActive ? 'rgba(239, 68, 68, 0.35)' : 'rgba(34, 211, 238, 0.2)';
            ctx.lineWidth = 1;
            ctx.setLineDash([5, 15]);
            ctx.stroke();
            ctx.restore();

            ctx.save();
            ctx.translate(centerX, centerY);
            ctx.rotate(-rotationTime * 0.5);
            ctx.beginPath();
            ctx.arc(0, 0, radius + 22, 0, Math.PI * 2);
            ctx.strokeStyle = currentOverloadActive ? 'rgba(249, 115, 22, 0.3)' : 'rgba(147, 51, 234, 0.15)';
            ctx.lineWidth = 1;
            ctx.setLineDash([15, 30]);
            ctx.stroke();
            ctx.restore();

            // Draw circular audio frequency bars
            const barCount = currentAudioData.length > 0 ? currentAudioData.length : 64;
            const angleStep = (Math.PI * 2) / barCount;
            
            for (let i = 0; i < barCount; i++) {
                // Get amplitude value (0 - 255)
                const val = currentAudioData[i] || 0;
                
                // Let's add a tiny bit of breathing noise if idle/silent
                let multiplier = val / 255;
                if (multiplier === 0 && currentIsListening) {
                    // Small noise for mic visual feedback
                    multiplier = (Math.sin(Date.now() / 150 + i) + 1) * 0.05;
                } else if (multiplier === 0 && !currentIsListening) {
                    // Idle breathing
                    multiplier = (Math.sin(Date.now() / 300 + i * 0.2) + 1) * 0.02;
                }

                // Bar length proportional to frequency value
                const maxBarLength = 80;
                const barLength = multiplier * maxBarLength;

                const angle = i * angleStep;
                const startX = centerX + Math.cos(angle) * radius;
                const startY = centerY + Math.sin(angle) * radius;
                const endX = centerX + Math.cos(angle) * (radius + barLength);
                const endY = centerY + Math.sin(angle) * (radius + barLength);

                // Draw line with a beautiful neon color gradient
                ctx.beginPath();
                ctx.moveTo(startX, startY);
                ctx.lineTo(endX, endY);
                
                let strokeColor;
                if (currentOverloadActive) {
                    const hue = (i / barCount) * 35; // Red-orange (0-35)
                    const flicker = Math.random() * 0.3;
                    strokeColor = `hsla(${hue}, 95%, 55%, ${0.4 + multiplier * 0.6 + flicker})`;
                } else {
                    const hue = (i / barCount) * 120 + 180; // Ranges from 180 (cyan) to 300 (magenta)
                    strokeColor = `hsla(${hue}, 90%, 65%, ${0.3 + multiplier * 0.7})`;
                }
                ctx.strokeStyle = strokeColor;
                ctx.lineWidth = Math.max(2, (w / barCount) * 0.6);
                ctx.lineCap = 'round';
                ctx.stroke();
            }

            // Draw Central pulsing ring
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
            ctx.strokeStyle = currentOverloadActive 
                ? 'rgba(239, 68, 68, 0.9)' 
                : (currentIsListening ? 'rgba(34, 211, 238, 0.8)' : 'rgba(34, 211, 238, 0.4)');
            ctx.lineWidth = currentOverloadActive ? 4 : 3;
            ctx.shadowBlur = currentOverloadActive ? 25 + currentIntensity * 30 : (currentIsListening ? 15 + currentIntensity * 20 : 8);
            ctx.shadowColor = currentOverloadActive ? '#ef4444' : '#22d3ee';
            ctx.stroke();
            ctx.shadowBlur = 0; // Reset shadow

            // Overload sparks / arcs
            if (currentOverloadActive && Math.random() > 0.45) {
                const arcCount = 2 + Math.floor(Math.random() * 4);
                for (let k = 0; k < arcCount; k++) {
                    const a = Math.random() * Math.PI * 2;
                    const rStart = radius * 0.95;
                    const rEnd = radius + 20 + Math.random() * 60;
                    ctx.beginPath();
                    ctx.moveTo(centerX + Math.cos(a) * rStart, centerY + Math.sin(a) * rStart);
                    ctx.lineTo(centerX + Math.cos(a + (Math.random() - 0.5) * 0.1) * rEnd, centerY + Math.sin(a) * rEnd);
                    ctx.strokeStyle = 'rgba(253, 224, 71, 0.85)'; // Yellow sparks
                    ctx.lineWidth = 1.5;
                    ctx.stroke();
                }
            }

            animationId = requestAnimationFrame(draw);
        };

        draw();
        return () => cancelAnimationFrame(animationId);
    }, [width, height]);

    return (
        <div className="relative" style={{ width, height }}>
            {/* Central Logo/Text */}
            <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
                <motion.div
                    animate={overloadActive ? { 
                        scale: [1, 1.12, 1],
                        filter: ["drop-shadow(0 0 12px rgba(239,68,68,0.8))", "drop-shadow(0 0 22px rgba(239,68,68,1))", "drop-shadow(0 0 12px rgba(239,68,68,0.8))"]
                    } : { 
                        scale: isListening ? [1, 1.1, 1] : 1 
                    }}
                    transition={overloadActive ? { duration: 0.6, repeat: Infinity, ease: "easeInOut" } : { duration: 2, repeat: Infinity, ease: "easeInOut" }}
                    className={`font-bold tracking-widest ${overloadActive ? 'text-red-400 font-black' : 'text-cyan-100 drop-shadow-[0_0_15px_rgba(34,211,238,0.8)]'}`}
                    style={{ fontSize: Math.min(width, height) * (overloadActive ? 0.07 : 0.1) }}
                >
                    {overloadActive ? (Math.random() > 0.88 ? "TEMP 99%" : (Math.random() > 0.88 ? "CRITICAL" : "OVERLOAD")) : "A.D.A"}
                </motion.div>
            </div>

            <canvas
                ref={canvasRef}
                style={{ width: '100%', height: '100%' }}
            />
        </div>
    );
};

export default Visualizer;
