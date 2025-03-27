#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-

__all__ = ()

import os

import aiohttp
import objects.logging
import objects.settings
import orjson
from quart import Quart
from quart import render_template

from objects.logging import Ansi
from objects.logging import log

from adapters.database import Database

from objects import glob

app = Quart(__name__)

objects.logging.configure_logging()

# used to secure session data.
# we recommend using a long randomly generated ascii string.
app.secret_key = objects.settings.SECRET_KEY

@app.before_serving
async def mysql_conn() -> None:
    glob.db = Database(objects.settings.DB_DSN)
    await glob.db.connect()
    log('Connected to MySQL!', Ansi.LGREEN)

@app.before_serving
async def http_conn() -> None:
    glob.http = aiohttp.ClientSession(json_serialize=lambda x: orjson.dumps(x).decode())
    log('Got our Client Session!', Ansi.LGREEN)

@app.after_serving
async def shutdown() -> None:
    await glob.db.disconnect()
    await glob.http.close()

# globals which can be used in template code
@app.template_global()
def appVersion() -> str:
    return objects.settings.VERSION

@app.template_global()
def appName() -> str:
    return objects.settings.APP_NAME

@app.template_global()
def captchaKey() -> str:
    return objects.settings.HCAPTCHA_SITE_KEY

@app.template_global()
def domain() -> str:
    return objects.settings.DOMAIN

from blueprints.frontend import frontend
app.register_blueprint(frontend)

from blueprints.admin import admin
app.register_blueprint(admin, url_prefix='/admin')

@app.errorhandler(404)
async def page_not_found(e):
    # NOTE: we set the 404 status explicitly
    return (await render_template('404.html'), 404)

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    app.run(port=8000, debug=objects.settings.DEBUG) # blocking call
