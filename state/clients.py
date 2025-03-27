from __future__ import annotations

import common.settings

from adapters.database import Database
from aiohttp import ClientSession

http_client: ClientSession
database = Database(common.settings.DB_DSN)
