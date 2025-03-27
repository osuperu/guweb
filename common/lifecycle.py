import aiohttp
import orjson
import state.clients

from common.logging import Ansi
from common.logging import log

async def _start_database() -> None:
    log("Connecting to MySQL...", Ansi.LBLUE)
    await state.clients.database.connect()
    log('Connected to MySQL!', Ansi.LGREEN)


async def _shutdown_database() -> None:
    log("Disconnecting from MySQL...", Ansi.LBLUE)
    await state.clients.database.disconnect()
    log('Disconnected from MySQL!', Ansi.LGREEN)


async def _start_http_client() -> None:
    log("Creating HTTP Client...", Ansi.LBLUE)
    state.clients.http_client = aiohttp.ClientSession(json_serialize=lambda x: orjson.dumps(x).decode())
    log('Got our client session!', Ansi.LGREEN)


async def _shutdown_http_client() -> None:
    log("Closing HTTP Client...", Ansi.LBLUE)
    await state.clients.http_client.close()
    log('Closed our client session!', Ansi.LGREEN)


async def start() -> None:
    await _start_database()
    await _start_http_client()


async def shutdown() -> None:
    await _shutdown_database()
    await _shutdown_http_client()