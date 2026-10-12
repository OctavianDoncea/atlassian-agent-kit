from fastapi import FastAPI
from agentkit.api.auth_routes import router as auth_router

app = FastAPI(title='AgentKit API', version='0.2.0')
app.include_router(auth_router)

@app.get('/health')
def health() -> dict:
    return {'status': 'ok'}