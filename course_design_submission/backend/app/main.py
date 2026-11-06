"""FastAPI 应用入口：只负责组装中间件、异常处理和 Controller。"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.controllers import auth_router, department_router, medical_router
from app.core.config import get_settings

settings=get_settings()
app=FastAPI(title=settings.app_name,version="1.0.0",docs_url="/docs")
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origin_list,allow_credentials=True,
                   allow_methods=["*"],allow_headers=["*"])


@app.exception_handler(HTTPException)
async def http_error(_request:Request,exc:HTTPException):
    return JSONResponse(status_code=exc.status_code,content={"detail":exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_error(_request:Request,exc:RequestValidationError):
    messages=[item["msg"].replace("Value error, ","") for item in exc.errors()]
    return JSONResponse(status_code=422,content={"detail":"；".join(messages),"errors":exc.errors()})


@app.get("/api/v1/health",tags=["系统"])
def health(): return {"status":"ok","message":"服务运行正常"}


app.include_router(auth_router,prefix="/api/v1")
app.include_router(department_router,prefix="/api/v1")
app.include_router(medical_router,prefix="/api/v1")
