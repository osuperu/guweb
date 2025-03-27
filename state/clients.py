from __future__ import annotations

from aiohttp import ClientSession

import common.settings
from adapters.database import Database

http_client: ClientSession
database = Database(common.settings.DB_DSN)
