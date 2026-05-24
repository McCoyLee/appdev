"""一个 FastAPI 起手项目。AI 可以扩展路由、加数据库、加业务逻辑。"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="My API")


class Health(BaseModel):
    status: str = "ok"


@app.get("/", response_model=Health)
async def root():
    return Health()


@app.get("/hello/{name}")
async def hello(name: str):
    return {"message": f"hello, {name}"}
