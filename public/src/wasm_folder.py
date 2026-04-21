import os
import anywidget
import asyncio
import marimo as mo
import js
from pyodide.ffi import to_js
from pyodide.ffi import create_proxy

_write_permission_event = asyncio.Event()
_channel_name = "marimo-mount"
_channel = js.BroadcastChannel.new(_channel_name)

def sync_filesystem(write=False):
    if write:
        js.eval("pyodide.FS.syncfs(0, (err) => { if (err) console.error(err); })")
    else:
        js.eval("pyodide.FS.syncfs(1, (err) => { if (err) console.error(err); })")

def listen_folder_mount(set_mount_path):

    async def on_message(event):
        data = event.data
        if data.type == "MOUNT_FOLDER":
            try:
                mount_path = "/mnt"
                if os.path.exists(mount_path):
                    js.self.pyodide.FS.unmount(mount_path)
                await js.self.pyodide.mountNativeFS(mount_path, data.handle)
                print(f"Successfully mounted to {mount_path} via BroadcastChannel")
                print("Mounted Files:", os.listdir(mount_path))
                set_mount_path(mount_path)
            except Exception as e:
                print(f"Mount error: {e}")
        elif data.type == "PERMISSION_RESULT":
            if data.status == "granted":
                _write_permission_event.set()
            else:
                print(f"PERMISSION_RESULT {data.status}")
        else:
            print(f"Unknown message {data.type}") 


    _channel.onmessage = create_proxy(on_message)

def folder_mount_iframe():

    the_html = """
        <span id="mount-container"></span>
        <script>
            function render(el) {
                let folderHandle = null;
                const bc = new BroadcastChannel('""" + _channel_name + """');
                const btn = document.createElement("button");
                btn.innerHTML = "📁 Mount Folder";
                btn.style.padding = "10px";
                btn.style.cursor = "pointer";
                btn.onclick = async () => {
                    try {
                        folderHandle = await window.showDirectoryPicker();
                        bc.postMessage({ type: "MOUNT_FOLDER", handle: folderHandle });
                        btn.innerHTML = "✅ Mounted " + folderHandle.name;
                        btn.style.background = "#d4edda";
                    } catch (e) {
                        btn.innerHTML = "❌ " + e.message;
                    }
                };
                bc.onmessage = async (event) => {
                    const msg = event.data;
                    if (msg.type === "REQUEST_WRITE" && folderHandle) {
                        try {
                            const status = await folderHandle.requestPermission({ mode: 'readwrite' });
                            bc.postMessage({ type: "PERMISSION_RESULT", status: status });
                        } catch (e) {
                            bc.postMessage({ type: "PERMISSION_RESULT", status: "error", error: e.message });
                        }
                    }
                };
                el.appendChild(btn);
            }
            const el = document.getElementById("mount-container");
            render(el);
        </script>
        """
    
    return mo.iframe(the_html, height="60px")


def folder_mount_widget():
    
    mount_button = anywidget.AnyWidget(
        _esm = """
        function render({ model, el }) {
            let folderHandle = null;
            const bc = new BroadcastChannel("marimo-mount");
            const btn = document.createElement("button");
            btn.innerHTML = "📁 Mount Folder";
            btn.style.padding = "10px";
            btn.style.cursor = "pointer";
            btn.onclick = async () => {
                try {
                    folderHandle = await window.showDirectoryPicker();
                    bc.postMessage({ type: "MOUNT_FOLDER", handle: folderHandle });
                    btn.innerHTML = "✅ Mounted " + folderHandle.name;
                    btn.style.background = "#d4edda";
                } catch (e) {
                    btn.innerHTML = "❌ " + e.message;
                }
            };
            model.on("msg:custom", async (msg) => {
                console.log("Upgrading handle", msg.type, folderHandle);
                if (msg.type === "REQUEST_WRITE" && folderHandle) {
                    try {
                        const status = await folderHandle.requestPermission({ mode: 'readwrite' });
                        bc.postMessage({ type: "PERMISSION_RESULT", status: status });
                    } catch (e) {
                        bc.postMessage({ type: "PERMISSION_RESULT", status: "error", error: e.message });
                        console.error(e);
                    }
                }
            });

            el.appendChild(btn);
        }
        export default { render };
        """
    )

    return mount_button

async def download_example_files_wasm_iframe(base_dir):

    _write_permission_event.clear()
    _channel.postMessage(to_js({"type": "REQUEST_WRITE"}, dict_converter=js.Object.fromEntries))
    await _write_permission_event.wait()
    await download_data_files(base_dir)
    sync_filesystem(True)

async def download_example_files_wasm_widget(base_dir, mount_widget):
    write_permission_event.clear()
    mount_widget.send({"type": "REQUEST_WRITE"})
    await write_permission_event.wait()
    await download_data_files(base_dir)
    sync_filesystem(True)


async def download_data_files(dest_path):
    print("download_data_files")
    import pyodide
    files = ["main.xlsx", "assets.xlsx", "indices.xlsx", "currencies.xlsx"]
    for file_name in files:
        file_url = str(mo.notebook_location() / "public" / "example" / file_name)
        response = await pyodide.http.pyfetch(file_url)
        with open(f"{dest_path}/{file_name}", "wb") as f:
            f.write(await response.bytes())
