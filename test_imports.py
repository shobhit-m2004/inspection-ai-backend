from app.main import app
from app.core.config import get_settings

print("✅ Backend imports OK")
print(f"App: {app.title}")
print(f"Version: {app.version}")

settings = get_settings()
print(f"Environment: {settings.APP_ENV}")
