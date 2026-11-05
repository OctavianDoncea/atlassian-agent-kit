from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agentkit.api.auth_routes import router as auth_router
from agentkit.api.eval_routes import router as eval_router
from agentkit.api.sync_routes import router as sync_router
from agentkit.api.plugins_routes import router as plugins_router
from agentkit.api.pii_routes import router as pii_router
from agentkit.api.usage_routes import router as usage_router

app = FastAPI(title='AgentKit API', version='0.2.0')

app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

app.include_router(auth_router)
app.include_router(eval_router)
app.include_router(sync_router)
app.include_router(plugins_router)
app.include_router(pii_router)
app.include_router(usage_router)

@app.get('/health')
def health() -> dict:
    return {'status': 'ok'}