const { contextBridge, ipcRenderer } = require('electron')

// Expose safe APIs to renderer
contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  getAppVersion: () => ipcRenderer.invoke('get-version')
})
