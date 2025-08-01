const { app, BrowserWindow, dialog, ipcMain } = require('electron')
const path = require('path')

function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  })

  win.webContents.openDevTools()
  win.loadURL('http://localhost:5173') // dev server
  //win.loadFile('../dist/index.html')

}

ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory']
  })
  return result.canceled ? null : result.filePaths[0]
})


app.whenReady().then(createWindow)
