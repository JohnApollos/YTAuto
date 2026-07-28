import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from autonomous_media.api.routes import router

app = FastAPI(title="Autonomous Media API")

# Include the API router
app.include_router(router)

# Mount the static frontend files
# In a real environment, `npm run build` must be executed first so the dist/ directory exists.
frontend_dist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(frontend_dist_path):
    # Mount the /assets directory and other static files
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
    # Catch-all route to serve index.html for React SPA client-side routing
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Allow serving standard files if they exist in dist root (like vite.svg, favicon, etc)
        file_path = os.path.join(frontend_dist_path, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Fallback to index.html
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))
else:
    @app.get("/")
    def no_frontend():
        return {"message": "Frontend not built. Run 'npm run build' inside the frontend directory."}
