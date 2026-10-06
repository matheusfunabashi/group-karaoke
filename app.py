"""Entry point: `python app.py` starts the whole app as a single process."""
import uvicorn

from karaoke import create_app
from karaoke.config import load_settings

settings = load_settings()
app = create_app(settings)

if __name__ == "__main__":
    # 0.0.0.0 so the app is reachable from outside a container (deployment contract §7.2).
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
