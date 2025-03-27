from __future__ import annotations

import tomllib

# app name
app_name = "guweb"

# secret key
secret_key = "changeme"

# hCaptcha settings:
hCaptcha_sitekey = "changeme"
hCaptcha_secret = "changeme"

# domain (used for api, avatar, etc)
domain = "gulag.ca"

# max image size for avatars, in megabytes
max_image_size = 2

# mysql credentials
mysql = {
    "db": "gulag",
    "host": "localhost",
    "user": "cmyui",
    "password": "changeme",
}

db_dsn = f"mysql://{mysql['user']}:{mysql['password']}@{mysql['host']}/{mysql['db']}"

# path to gulag root (must have leading and following slash)
path_to_gulag = "/path/to/gulag/"

# enable debug (disable when in production to improve performance)
debug = False

log_with_colors = True

# disallowed names (hardcoded banned usernames)
disallowed_names = {"cookiezi", "rrtyui", "hvick225", "qsc20010"}

# disallowed passwords (hardcoded banned passwords)
disallowed_passwords = {"password", "minilamp"}

# enable registration
registration = True

# social links (used throughout guweb)
github = "https://github.com/varkaria/guweb"
discord_server = "https://discord.com/invite/Y5uPvcNpD9"
youtube = "https://youtube.com/"
twitter = "https://twitter.com/"
instagram = "https://instagram.com/"

with open("pyproject.toml", "rb") as f:
    version = tomllib.load(f)["tool"]["poetry"]["version"]
