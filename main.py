#!/usr/bin/env python3.13

from __future__ import annotations

__all__ = ()

import os

from quart import Quart
from quart import render_template

import common.logging
import common.settings
from common import lifecycle

app = Quart(__name__)

common.logging.configure_logging()

# used to secure session data.
# we recommend using a long randomly generated ascii string.
app.secret_key = common.settings.SECRET_KEY


@app.before_serving
async def startup() -> None:
    await lifecycle.start()


@app.after_serving
async def shutdown() -> None:
    await lifecycle.shutdown()


# globals which can be used in template code
@app.template_global()
def appVersion() -> str:
    return common.settings.VERSION


@app.template_global()
def appName() -> str:
    return common.settings.APP_NAME


@app.template_global()
def captchaKey() -> str:
    return common.settings.HCAPTCHA_SITE_KEY


@app.template_global()
def domain() -> str:
    return common.settings.DOMAIN


from blueprints.frontend import frontend

app.register_blueprint(frontend)

from blueprints.admin import admin

app.register_blueprint(admin, url_prefix="/admin")


@app.errorhandler(404)
async def page_not_found(e):
    # NOTE: we set the 404 status explicitly
    return (await render_template("404.html"), 404)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    app.run(
        host=common.settings.APP_HOST,
        port=common.settings.APP_PORT,
        debug=common.settings.DEBUG,
    )  # blocking call
