import httpx
import pytest

from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    # 서버를 띄우지 않고 ASGI 앱을 직접 호출한다. 실제 HTTP 계층과 같은 코드 경로를 탄다
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
