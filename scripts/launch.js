const { spawn } = require('child_process');
const path = require('path');

// Ensure ELECTRON_RUN_AS_NODE is completely removed so Electron runs as a desktop GUI app
delete process.env.ELECTRON_RUN_AS_NODE;

const isDev = process.argv.includes('--dev') || process.env.NODE_ENV !== 'production';
const electronBinary = require('electron');

if (isDev) {
    const concurrently = require('concurrently');
    const { result } = concurrently(
        [
            { command: 'npx vite', name: 'Vite', prefixColor: 'cyan' },
            { command: `npx wait-on tcp:5173 && "${electronBinary}" .`, name: 'App', prefixColor: 'green' }
        ],
        {
            killOthers: ['failure', 'success'],
            restartTries: 0,
            env: process.env
        }
    );
    result.catch(() => {});
} else {
    const child = spawn(electronBinary, ['.'], {
        stdio: 'inherit',
        env: process.env
    });
    child.on('exit', (code) => process.exit(code || 0));
}
