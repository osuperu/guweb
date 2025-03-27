from __future__ import annotations

import os
import tomllib
from urllib.parse import quote

from dotenv import load_dotenv

from common.settings_utils import read_bool
from common.settings_utils import read_list

load_dotenv()

APP_NAME = os.environ["APP_NAME"]

APP_HOST = os.environ["APP_HOST"]
APP_PORT = int(os.environ["APP_PORT"])

SECRET_KEY = os.environ["SECRET_KEY"]

HCAPTCHA_SITE_KEY = os.environ["HCAPTCHA_SITE_KEY"]
HCAPTCHA_SECRET = os.environ["HCAPTCHA_SECRET"]

DOMAIN = os.environ["DOMAIN"]

MAX_IMAGE_SIZE = int(os.environ["MAX_IMAGE_SIZE"])

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ["DB_PORT"])
DB_USER = os.environ["DB_USER"]
DB_PASS = quote(os.environ["DB_PASS"])
DB_NAME = os.environ["DB_NAME"]
DB_DSN = f"mysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

PATH_TO_BPY = os.environ["PATH_TO_BPY"]

DEBUG = read_bool(os.environ["DEBUG"])

LOG_WITH_COLORS = read_bool(os.environ["LOG_WITH_COLORS"])

DISALLOWED_USERNAMES = read_list(os.environ["DISALLOWED_USERNAMES"])
DISALLOWED_PASSWORDS = read_list(os.environ["DISALLOWED_PASSWORDS"])

ALLOW_REGISTRATION = read_bool(os.environ["ALLOW_REGISTRATION"])

GITHUB = os.environ["GITHUB"]
DISCORD_SERVER = os.environ["DISCORD_SERVER"]
YOUTUBE = os.environ["YOUTUBE"]
TWITTER = os.environ["TWITTER"]
INSTAGRAM = os.environ["INSTAGRAM"]

with open("pyproject.toml", "rb") as f:
    VERSION = tomllib.load(f)["tool"]["poetry"]["version"]
