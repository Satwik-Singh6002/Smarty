import React, { useEffect, useRef, useState } from 'react';
import { Copy, Check } from 'lucide-react';

const ChatModule = ({
    messages,
    inputValue,
    setInputValue,
    handleSend,
    isModularMode,
    activeDragElement,
    position,
    width = 672, // default max-w-2xl
    height,
    onMouseDown,
    isProcessing = false,
}) => {
    const messagesEndRef = useRef(null);
    const [copiedIndex, setCopiedIndex] = useState(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const copyToClipboard = (text, index) => {
        navigator.clipboard.writeText(text).then(() => {
            setCopiedIndex(index);
            setTimeout(() => setCopiedIndex(null), 2000);
        });
    };

    const getRelativeTime = (timeStr) => {
        // timeStr is from toLocaleTimeString
        // Show as-is for simplicity — could be enhanced with date-fns
        return timeStr;
    };

    return (
        <div
            id="chat"
            onMouseDown={onMouseDown}
            className={`absolute px-6 py-4 pointer-events-auto transition-all duration-200 
            glass rounded-2xl
            ${isModularMode ? (activeDragElement === 'chat' ? 'ring-2 ring-green-500' : 'ring-1 ring-yellow-500/30') : ''}
        `}
            style={{
                left: position.x,
                top: position.y,
                transform: 'translate(-50%, 0)', // Aligned top-center
                width: width,
                height: height
            }}
        >
            <div className="absolute inset-0 bg-[url('/noise.svg')] opacity-5 pointer-events-none mix-blend-overlay rounded-2xl"></div>

            <div
                className="flex flex-col gap-3 overflow-y-auto mb-4 scrollbar-hide mask-image-gradient relative z-10"
                style={{ height: height ? `calc(${height}px - 70px)` : '15rem' }}
            >
                {messages.slice(-20).map((msg, i) => (
                    <div key={i} className="text-sm border-l-2 border-cyan-800/50 pl-3 py-1 group animate-fade-in relative">
                        <div className="flex items-center justify-between">
                            <div>
                                <span className="text-cyan-600 text-xs opacity-70">[{getRelativeTime(msg.time)}]</span>{' '}
                                <span className={`font-bold drop-shadow-sm ${msg.sender === 'You' ? 'text-blue-300' : msg.sender === 'System' ? 'text-yellow-400' : 'text-cyan-300'}`}>
                                    {msg.sender}
                                </span>
                            </div>
                            {msg.sender !== 'You' && msg.sender !== 'System' && (
                                <button
                                    onClick={() => copyToClipboard(msg.text, i)}
                                    className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-cyan-500/10 text-cyan-600"
                                    title="Copy message"
                                >
                                    {copiedIndex === i ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                                </button>
                            )}
                        </div>
                        <div className="text-gray-300 mt-1 leading-relaxed whitespace-pre-wrap">{msg.text}</div>
                    </div>
                ))}

                {/* Typing Indicator */}
                {isProcessing && (
                    <div className="text-sm border-l-2 border-cyan-800/50 pl-3 py-1 animate-fade-in">
                        <span className="font-bold text-cyan-300 drop-shadow-sm">Smarty</span>
                        <div className="mt-2 flex items-center gap-1.5">
                            <span className="typing-dot"></span>
                            <span className="typing-dot"></span>
                            <span className="typing-dot"></span>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            <div className="flex gap-2 relative z-10 absolute bottom-4 left-6 right-6">
                <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleSend}
                    placeholder="Type a command..."
                    className="flex-1 bg-black/40 border border-cyan-700/30 rounded-lg p-3 text-cyan-50 focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/50 transition-all placeholder-cyan-800/50 backdrop-blur-sm text-sm"
                />
            </div>
            {isModularMode && <div className={`absolute -top-6 left-0 text-xs font-bold tracking-widest ${activeDragElement === 'chat' ? 'text-green-500' : 'text-yellow-500/50'}`}>CHAT MODULE</div>}
        </div>
    );
};

export default React.memo(ChatModule);
