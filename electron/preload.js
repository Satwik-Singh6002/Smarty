const { contextBridge, ipcRenderer } = require('electron');

/**
 * Secure IPC Bridge for Smarty
 * 
 * This preload script runs in a sandboxed context and exposes only
 * the specific IPC channels the renderer process needs.
 * 
 * The renderer process accesses these via `window.electronAPI.*`
 */
contextBridge.exposeInMainWorld('electronAPI', {
    // Window Controls
    minimize: () => ipcRenderer.send('window-minimize'),
    maximize: () => ipcRenderer.send('window-maximize'),
    close: () => ipcRenderer.send('window-close'),

    // Platform detection
    platform: process.platform,

    // App version
    getVersion: () => ipcRenderer.invoke('get-app-version'),

    // Open External URL
    openExternal: (url) => ipcRenderer.send('open-external', url),
});
