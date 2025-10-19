import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.json_data = {"example": "value", "number": 42, "nested": {"key": "value"}}
    app.state.clients = set()
    app.state.lock = asyncio.Lock()

    yield

app = FastAPI(lifespan=lifespan)

async def broadcast_current():
    text = json.dumps(app.state.json_data)
    for ws in app.state.clients.copy():
        try:
            await ws.send_text(text)
        except:
            app.state.clients.discard(ws)

@app.get("/config")
async def get_json():
    return app.state.json_data


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    app.state.clients.add(websocket)
    await websocket.send_text(json.dumps(app.state.json_data))
    try:
        while True:
            data_text = await websocket.receive_text()
            new_data = json.loads(data_text)
            async with app.state.lock:
                app.state.json_data = new_data
            await broadcast_current()
    except WebSocketDisconnect:
        app.state.clients.discard(websocket)


@app.get("/", response_class=HTMLResponse)
async def get_editor():
    return html

html = """\
<!DOCTYPE html>
<html>
<head>
    <title>Config Editor</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/jsoneditor@9.10.3/dist/jsoneditor.min.css">
    <script src="https://cdn.jsdelivr.net/npm/jsoneditor@9.10.3/dist/jsoneditor.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #jsoneditor { width: 100%; height: 500px; }
        .info { margin-bottom: 20px; padding: 10px; background: #f0f0f0; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="info">
        <h2>Real-time Config Editor</h2>
        <p>API для получения JSON: <a href="/config" target="_blank" rel="noopener noreferrer">GET /config</a></p>
    </div>
    <div id="jsoneditor"></div>

    <script>
        const container = document.getElementById('jsoneditor');
        const options = {
            mode: 'tree',
            modes: ['code', 'tree', 'view'],
            onChange: function() {
                try {
                    const json = editor.get();
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify(json));
                    }
                } catch (e) {
                    console.error('Invalid JSON');
                }
            }
        };
        
        const editor = new JSONEditor(container, options);

        const ws = new WebSocket(`ws://${window.location.host}/ws`);

        ws.onmessage = function(event) {
            const json = JSON.parse(event.data);
            const currentJson = JSON.stringify(editor.get());
            const newJson = JSON.stringify(json);
            if (currentJson !== newJson) {
                editor.set(json);
            }
        };

        ws.onerror = function(error) {
            console.error('WebSocket error:', error);
        };

        ws.onclose = function() {
            console.log('WebSocket connection closed');
        };
    </script>
</body>
</html>\
"""
