import React from 'react';
import { Mic, MicOff, Settings, Power, Video, VideoOff, Hand, Lightbulb, Printer, Globe, Box } from 'lucide-react';

const ToolButton = ({ onClick, isActive, disabled, activeClass, label, children }) => (
    <div className="tooltip-wrapper">
        <button
            onClick={onClick}
            disabled={disabled}
            className={`p-3 rounded-full border-2 transition-all duration-300 active:scale-90 ${
                disabled
                    ? 'border-gray-800 text-gray-800 cursor-not-allowed'
                    : isActive
                        ? activeClass
                        : 'border-cyan-900 text-cyan-700 hover:border-cyan-500 hover:text-cyan-500'
            }`}
        >
            {children}
        </button>
        <span className="tooltip-text">{label}</span>
    </div>
);

const ToolsModule = ({
    isConnected,
    isMuted,
    isVideoOn,
    isHandTrackingEnabled,
    showSettings,
    onTogglePower,
    onToggleMute,
    onToggleVideo,
    onToggleSettings,

    onToggleHand,
    onToggleKasa,
    showKasaWindow,
    onTogglePrinter,
    showPrinterWindow,
    onToggleCad,
    showCadWindow,
    onToggleBrowser,
    showBrowserWindow,
    activeDragElement,

    position,
    onMouseDown
}) => {
    return (
        <div
            id="tools"
            onMouseDown={onMouseDown}
            className={`absolute px-6 py-3 transition-all duration-200 
                        glass rounded-full`}
            style={{
                left: position.x,
                top: position.y,
                transform: 'translate(-50%, -50%)',
                pointerEvents: 'auto'
            }}
        >
            <div className="absolute inset-0 bg-[url('/noise.svg')] opacity-5 pointer-events-none mix-blend-overlay rounded-full"></div>

            <div className="flex justify-center gap-5 relative z-10">
                {/* Power Button */}
                <ToolButton
                    onClick={onTogglePower}
                    isActive={isConnected}
                    activeClass="border-green-500 bg-green-500/10 text-green-500 hover:bg-green-500/20 shadow-[0_0_15px_rgba(34,197,94,0.3)]"
                    label={isConnected ? 'Disconnect' : 'Connect'}
                >
                    <Power size={22} />
                </ToolButton>

                {/* Mute Button */}
                <ToolButton
                    onClick={onToggleMute}
                    disabled={!isConnected}
                    isActive={isConnected && !isMuted}
                    activeClass={isMuted
                        ? 'border-red-500 bg-red-500/10 text-red-500 hover:bg-red-500/20 shadow-[0_0_15px_rgba(239,68,68,0.3)]'
                        : 'border-cyan-500 bg-cyan-500/10 text-cyan-500 hover:bg-cyan-500/20 shadow-[0_0_15px_rgba(6,182,212,0.3)]'
                    }
                    label={isMuted ? 'Unmute (Ctrl+M)' : 'Mute (Ctrl+M)'}
                >
                    {isMuted ? <MicOff size={22} /> : <Mic size={22} />}
                </ToolButton>

                {/* Video Button */}
                <ToolButton
                    onClick={onToggleVideo}
                    isActive={isVideoOn}
                    activeClass="border-purple-500 bg-purple-500/10 text-purple-500 hover:bg-purple-500/20 shadow-[0_0_15px_rgba(168,85,247,0.3)]"
                    label={isVideoOn ? 'Stop Camera' : 'Start Camera'}
                >
                    {isVideoOn ? <Video size={22} /> : <VideoOff size={22} />}
                </ToolButton>

                {/* Settings Button */}
                <ToolButton
                    onClick={onToggleSettings}
                    isActive={showSettings}
                    activeClass="border-cyan-400 text-cyan-400 bg-cyan-900/20"
                    label="Settings (Esc to close)"
                >
                    <Settings size={22} />
                </ToolButton>

                {/* Hand Tracking Toggle */}
                <ToolButton
                    onClick={onToggleHand}
                    isActive={isHandTrackingEnabled}
                    activeClass="border-orange-500 bg-orange-500/10 text-orange-500 hover:bg-orange-500/20 shadow-[0_0_15px_rgba(249,115,22,0.3)]"
                    label="Gesture Control"
                >
                    <Hand size={22} />
                </ToolButton>

                {/* Kasa Light Control */}
                <ToolButton
                    onClick={onToggleKasa}
                    isActive={showKasaWindow}
                    activeClass="border-yellow-300 bg-yellow-300/10 text-yellow-300 hover:bg-yellow-300/20 shadow-[0_0_15px_rgba(253,224,71,0.3)]"
                    label="Smart Home"
                >
                    <Lightbulb size={22} />
                </ToolButton>

                {/* 3D Printer Control */}
                <ToolButton
                    onClick={onTogglePrinter}
                    isActive={showPrinterWindow}
                    activeClass="border-green-400 bg-green-400/10 text-green-400 hover:bg-green-400/20"
                    label="3D Printer"
                >
                    <Printer size={22} />
                </ToolButton>

                {/* CAD Agent Toggle */}
                <ToolButton
                    onClick={onToggleCad}
                    isActive={showCadWindow}
                    activeClass="border-cyan-400 bg-cyan-400/10 text-cyan-400 hover:bg-cyan-400/20 shadow-[0_0_15px_rgba(34,211,238,0.3)]"
                    label="CAD Generator"
                >
                    <Box size={22} />
                </ToolButton>

                {/* Web Agent Toggle */}
                <ToolButton
                    onClick={onToggleBrowser}
                    isActive={showBrowserWindow}
                    activeClass="border-blue-400 bg-blue-400/10 text-blue-400 hover:bg-blue-400/20 shadow-[0_0_15px_rgba(96,165,250,0.3)]"
                    label="Web Agent"
                >
                    <Globe size={22} />
                </ToolButton>
            </div>
        </div>
    );
};

export default React.memo(ToolsModule);
