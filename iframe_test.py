import marimo

__generated_with = "0.23.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import js
    from pyodide.ffi import create_proxy

    _channel = js.BroadcastChannel.new("my-channel")
    async def on_message(event):
        data = event.data
        if data.type == "TEST":
            print("TEST MESSAGE!")
        else:
            print(f"Unknown message {data.type}") 


    _channel.onmessage = create_proxy(on_message)


    the_html = """
        <span id="my-container"></span>
        <script>
            function render(el) {
                let folderHandle = null;
                const bc = new BroadcastChannel('my-channel');
                const btn = document.createElement("button");
                btn.innerHTML = "Click me";
                btn.style.padding = "10px";
                btn.style.cursor = "pointer";
                btn.onclick = async () => {
                    try {
                        bc.postMessage({ type: "TEST" });
                        btn.innerHTML = "Clicked!";
                        btn.style.background = "#d4edda";
                    } catch (e) {
                        btn.innerHTML = "❌ " + e.message;
                    }
                };
                el.appendChild(btn);
            }
            const el = document.getElementById("my-container");
            console.log("el", el);
            render(el);
        </script>
        """

    mo.iframe(the_html, height="60px")

    return


if __name__ == "__main__":
    app.run()
