from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db

# 确保所有模型被导入以注册到 Base.metadata
import backend.app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    yield


app = FastAPI(
    title="QA Master",
    description="QA 团队测试管理平台 - 测试用例自动化生成与执行",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 API 路由
from backend.app.api.v1.requirements import router as requirements_router
from backend.app.api.v1.specs import router as specs_router
from backend.app.api.v1.testcases import router as testcases_router
from backend.app.api.v1.generation import router as generation_router
from backend.app.api.v1.execution import router as execution_router
from backend.app.api.v1.notifications import router as notifications_router
from backend.app.api.v1.dashboard import router as dashboard_router

app.include_router(requirements_router, prefix="/api/v1")
app.include_router(specs_router, prefix="/api/v1")
app.include_router(testcases_router, prefix="/api/v1")
app.include_router(generation_router, prefix="/api/v1")
app.include_router(execution_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "QA Master API", "version": "0.1.0", "docs": "/docs"}
