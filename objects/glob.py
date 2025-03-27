# -*- coding: utf-8 -*-

__all__ = ('db', 'http', 'cache')

from typing import TYPE_CHECKING

import config  # imported for indirect use

if TYPE_CHECKING:
    from adapters.database import Database
    from aiohttp import ClientSession

db: 'Database'
http: 'ClientSession'

cache = {
    'bcrypt': {}
}
