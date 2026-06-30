import os
import sys
import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

print("=== AEGIS API STARTING ===")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")

app = FastAPI(title="AEGIS API", version="0.2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("\n--- Attempting router imports ---")
try:
    from routers import threads, fleet
    app.include_router(threads.router)
    app.include_router(fleet.router)
    print("✅ SUCCESS: Imported threads and fleet routers")
except Exception as e:
    print(f"❌ FAILED: Router import error - {type(e).__name__}: {e}")
    traceback.print_exc()

print("\n--- Attempting LangServe import ---")
try:
    from langserve import add_routes
    print("✅ SUCCESS: langserve imported")
except Exception as e:
    print(f"❌ FAILED: LangServe import error - {type(e).__name__}: {e}")
    traceback.print_exc()

print("\n=== AEGIS API INITIALIZATION COMPLETE ===\n")

@app.get("/")
async def root():
    return {"status": "online", "message": "AEGIS API is running", "docs": "/docs", "version": "0.2.1"}

@app.get("/health")
def health():
    return {"status": "ok", "products": ["Engine", "Observability", "Evaluation", "Deployment", "Sandboxes", "Fleet", "deepagents", "langgraph", "langchain"], "version": "0.2.1"}

@app.get("/debug")
def debug_info():
    return {"cwd": os.getcwd(), "pythonpath": os.environ.get("PYTHONPATH"), "python_version": sys.version}
