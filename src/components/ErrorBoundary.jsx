import React from 'react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        this.setState({ errorInfo });
        console.error('[Smarty] Render Error:', error, errorInfo);
    }

    handleRestart = () => {
        this.setState({ hasError: false, error: null, errorInfo: null });
    };

    render() {
        if (this.state.hasError) {
            return (
                <div className="h-screen w-screen bg-black flex flex-col items-center justify-center font-mono text-cyan-100 select-none">
                    {/* Background */}
                    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-red-950/30 via-black to-black pointer-events-none" />

                    <div className="relative z-10 flex flex-col items-center gap-6 p-10 border border-red-500/30 rounded-2xl bg-black/80 backdrop-blur-xl shadow-[0_0_60px_rgba(239,68,68,0.15)] max-w-lg">
                        {/* Error Icon */}
                        <div className="w-16 h-16 rounded-full border-2 border-red-500/60 flex items-center justify-center">
                            <span className="text-3xl text-red-400">⚠</span>
                        </div>

                        <h1 className="text-2xl font-bold tracking-[0.2em] text-red-400 drop-shadow-[0_0_15px_rgba(239,68,68,0.5)]">
                            SYSTEM ERROR
                        </h1>

                        <p className="text-sm text-gray-400 text-center leading-relaxed max-w-sm">
                            Something went wrong in the interface. This is usually temporary — click below to restart.
                        </p>

                        {/* Error Details (collapsed) */}
                        <details className="w-full text-xs">
                            <summary className="text-cyan-600 cursor-pointer hover:text-cyan-400 transition-colors">
                                Technical Details
                            </summary>
                            <pre className="mt-2 p-3 bg-gray-900/80 rounded border border-gray-800 text-red-300/80 overflow-x-auto max-h-32 overflow-y-auto text-[10px] leading-relaxed">
                                {this.state.error?.toString()}
                                {'\n\n'}
                                {this.state.errorInfo?.componentStack}
                            </pre>
                        </details>

                        {/* Restart Button */}
                        <button
                            onClick={this.handleRestart}
                            className="px-8 py-3 bg-cyan-500/10 border border-cyan-500/40 rounded-lg text-cyan-400 font-mono text-sm uppercase tracking-widest hover:bg-cyan-500/20 hover:border-cyan-400 transition-all shadow-[0_0_20px_rgba(6,182,212,0.1)] active:scale-95"
                        >
                            Restart Interface
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
