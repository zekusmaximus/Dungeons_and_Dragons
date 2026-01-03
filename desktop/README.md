# Windows Desktop Build

This folder packages the FastAPI backend and Vite UI into a Windows EXE using Electron + electron-builder (NSIS).

## Prerequisites (build machine)
- Node.js 18+
- Python 3.10+ available on PATH (for the build step only)
- `npm install` run in `ui/` and `desktop/`

## Build steps
1) Build the UI once:
```bash
npm --prefix ../ui install
npm --prefix ../ui run build
```

2) Install desktop build deps:
```bash
npm install
```

3) Prepare embedded Python (downloads embeddable Python + installs backend deps):
```bash
npm run prepare:python
```

4) Build the Windows EXE (NSIS):
```bash
npm run dist
```

Outputs land under `desktop/dist/`.

## Bundled Python
The `prepare:python` script downloads the embeddable distribution to `desktop/python/` and installs backend dependencies into it.
You can override the version:
```bash
powershell -ExecutionPolicy Bypass -File scripts/prepare_windows_python.ps1 -PythonVersion 3.11.8
```

## Runtime behavior
- On first run, the app asks for a data folder and copies seed assets into it.
- The backend serves the UI on `http://127.0.0.1:8000` and stores sessions/data under the chosen folder.
