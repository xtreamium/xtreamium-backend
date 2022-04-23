import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi_utils.tasks import repeat_every

from .utils.epg.epg import EPGParser
from .utils.streamer import Streamer
from .utils.xtream import XTream

DEBUG_EPG_URL = "http://fingerfish.xyz/"

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)

epg = EPGParser(
    DEBUG_EPG_URL
)
app = FastAPI()
origins = [
    "https://dev-streams.fergl.ie:3000",
    "https://streams.fergl.ie",
    "http://127.0.0.1:35729",
    "http://localhost:35729",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def __get_provider(request: Request):
    return XTream(
        request.headers.get("x-xtream-server"),
        request.headers.get("x-xtream-username"),
        request.headers.get("x-xtream-password"),
    )


@app.on_event("startup")
@repeat_every(seconds=60 * 60)  # every hour
def update_epg_task() -> None:
    logger.debug("Caching EPG task started")
    epg.cache_epg()
    logger.debug("Caching EPG task ended")


@app.get("/epg/{channel_id}")
async def get_channel_epg(channel_id):
    listings = epg.get_listings(channel_id)
    return sorted(listings, key=lambda l: l['start'])


@app.get("/ping")
async def ping():
    return "pong"


@app.get("/validate")
async def validate_crendentials(request: Request, response: Response):
    try:
        provider = __get_provider(request)
        categories = provider.get_categories().json()
        if type(categories) is list:
            return {"status": "accepted"}
    except ValueError as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)

    response.status_code = 401
    return {"status": "denied"}


@app.get("/channels")
async def channels(request: Request):
    provider = __get_provider(request)
    categories = provider.get_categories()
    return categories.json()


@app.get("/streams/{category_id}")
async def read_item(category_id, request: Request):
    provider = __get_provider(request)
    streams = provider.get_streams_for_category(category_id)
    return streams.json()


@app.get("/live/stream/{stream_id}")
async def get_live_stream(stream_id: str, request: Request):
    provider = __get_provider(request)
    url = provider.get_live_stream_url(stream_id)
    return StreamingResponse(Streamer.receive_stream(url), media_type="video/mp2t")


@app.get("/live/stream/url/{stream_id}")
async def get_live_stream(stream_id: str, request: Request):
    provider = __get_provider(request)
    url = provider.get_live_stream_url(stream_id)
    return {
        "url": url
    }
