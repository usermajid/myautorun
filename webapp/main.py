from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates # If you want to render templates from backend

import logging

# Configure logging
logger = logging.getLogger(__name__)
# Basic logging setup (customize as needed)
logging.basicConfig(level=logging.INFO)


app = FastAPI()

# Mount static files (CSS, JS, images for your webapp)
# This assumes you have a 'static' directory inside 'webapp'
# The path "/static" in the URL will serve files from "webapp/static" directory.
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")

# Optional: Setup Jinja2 templates if you plan to render HTML from FastAPI backend
# templates = Jinja2Templates(directory="webapp/templates") # if you have a templates dir

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    logger.info("Root path '/' accessed. Serving index.html.")
    # This is a very basic way to serve an HTML file.
    # For more complex apps, you might use Jinja2 templates or a JS framework.
    try:
        with open("webapp/static/index.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        logger.error("webapp/static/index.html not found.")
        return HTMLResponse(content="<h1>WebApp not found</h1><p>Please ensure webapp/static/index.html is present.</p>", status_code=404)
    except Exception as e:
        logger.error(f"Error serving index.html: {e}", exc_info=True)
        return HTMLResponse(content="<h1>Internal Server Error</h1><p>Sorry, something went wrong.</p>", status_code=500)

@app.get("/api/hello")
async def hello_world_api():
    logger.info("API endpoint /api/hello accessed.")
    return {"message": "Hello World from FastAPI WebApp"}

# Example: Endpoint to receive data from Telegram Web App
@app.post("/api/submitdata")
async def submit_data(request: Request):
    try:
        data = await request.json()
        logger.info(f"Received data from WebApp: {data}")
        # Process the data here (e.g., save to database, interact with bot)
        # user_id = data.get('user', {}).get('id')
        # query_id = data.get('query_id') # Important for answering webapp queries if needed by PTB
        
        # For now, just echo it back with a success message
        return {"status": "success", "received_data": data}
    except Exception as e:
        logger.error(f"Error processing submitted data: {e}", exc_info=True)
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server for WebApp using Uvicorn...")
    # This is for local development. For production, consider Gunicorn or other ASGI servers.
    # The port should be different from your bot if running on the same machine without a reverse proxy.
    # Example: uvicorn.run("webapp.main:app", host="0.0.0.0", port=8080, reload=True)
    # The reload=True flag is useful for development to automatically reload on code changes.
    uvicorn.run(app, host="0.0.0.0", port=8000) # Standard port for FastAPI examples
    # Note: The application string for uvicorn should be "main:app" if you run it from outside the webapp dir.
    # e.g., from project root: python -m uvicorn webapp.main:app --reload
    # If running `python webapp/main.py` directly, then `uvicorn.run(app, ...)` is fine.
