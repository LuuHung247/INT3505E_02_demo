from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!doctype html>
<html>
  <head><meta charset="utf-8"><title>Code on Demand Demo</title></head>
  <body>
    <h1>Code on Demand (REST constraint)</h1>
    <button id="btn">Run code</button>

    <script type="module">
      document.getElementById('btn').addEventListener('click', async () => {
        const mod = await import('/code.js');
        mod.greet('Alice');
      });
    </script>
  </body>
</html>
"""

@app.get("/code.js")
def code_js():
    js = """
export function greet(name) {
  alert(`Hello, ${name}! This is greet() function from server.`);
}
"""
    return Response(js, media_type="text/javascript")