const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn } = require('child_process');

const API_HOST = '127.0.0.1';
const API_PORT = 8000;
let backendProcess = null;

const loadConfig = () => {
  const configPath = path.join(app.getPath('userData'), 'config.json');
  if (!fs.existsSync(configPath)) return {};
  try {
    return JSON.parse(fs.readFileSync(configPath, 'utf8'));
  } catch (err) {
    return {};
  }
};

const saveConfig = (config) => {
  const configPath = path.join(app.getPath('userData'), 'config.json');
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
};

const pickDataRoot = async () => {
  const config = loadConfig();
  if (config.dataRoot && fs.existsSync(config.dataRoot)) {
    return config.dataRoot;
  }
  const result = await dialog.showOpenDialog({
    title: 'Choose your adventure folder',
    properties: ['openDirectory', 'createDirectory'],
  });
  if (result.canceled || !result.filePaths.length) {
    return null;
  }
  const dataRoot = result.filePaths[0];
  saveConfig({ ...config, dataRoot });
  return dataRoot;
};

const waitForServer = () => new Promise((resolve, reject) => {
  const started = Date.now();
  const check = () => {
    const req = http.get(
      { hostname: API_HOST, port: API_PORT, path: '/health', timeout: 1000 },
      (res) => {
        if (res.statusCode === 200) {
          res.resume();
          resolve();
          return;
        }
        res.resume();
        retry();
      },
    );
    req.on('error', retry);
    req.on('timeout', () => {
      req.destroy();
      retry();
    });
  };
  const retry = () => {
    if (Date.now() - started > 20000) {
      reject(new Error('Timed out waiting for backend'));
      return;
    }
    setTimeout(check, 500);
  };
  check();
});

const resolveBackendRoot = () => {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend');
  }
  return path.resolve(__dirname, '..');
};

const resolvePythonBin = () => {
  if (app.isPackaged) {
    const bundledPython = path.join(process.resourcesPath, 'python', 'python.exe');
    if (fs.existsSync(bundledPython)) {
      return bundledPython;
    }
  }
  return process.env.DM_DESKTOP_PYTHON || 'python';
};

const startBackend = (dataRoot) => {
  const backendRoot = resolveBackendRoot();
  const pythonBin = resolvePythonBin();
  const env = {
    ...process.env,
    DM_SERVICE_REPO_ROOT: backendRoot,
    DM_SERVICE_DATA_ROOT: dataRoot,
    DM_SERVICE_SEED_ROOT: backendRoot,
  };
  backendProcess = spawn(
    pythonBin,
    ['-m', 'uvicorn', 'service.app:app', '--host', API_HOST, '--port', String(API_PORT)],
    { cwd: backendRoot, env, stdio: 'inherit' },
  );
  backendProcess.on('exit', () => {
    backendProcess = null;
  });
};

const createWindow = async () => {
  const dataRoot = await pickDataRoot();
  if (!dataRoot) {
    app.quit();
    return;
  }
  startBackend(dataRoot);
  try {
    await waitForServer();
  } catch (err) {
    dialog.showErrorBox('Backend Error', String(err));
    app.quit();
    return;
  }
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    },
  });
  await win.loadURL(`http://${API_HOST}:${API_PORT}`);
};

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (backendProcess) {
    backendProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
