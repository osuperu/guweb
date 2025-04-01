from __future__ import annotations

__all__ = ()

import datetime
import hashlib
import os
import time
from functools import wraps
from pathlib import Path

import bcrypt
import timeago
from PIL import Image
from quart import Blueprint
from quart import redirect
from quart import render_template
from quart import request
from quart import send_file
from quart import session

import common.settings
import state.cache
import state.clients
from common import utils
from common.logging import Ansi
from common.logging import log
from common.privileges import Privileges
from common.utils import flash
from common.utils import flash_with_customizations
from constants import regexes

VALID_MODES = frozenset({"std", "taiko", "catch", "mania"})
VALID_MODS = frozenset({"vn", "rx", "ap"})

frontend = Blueprint("frontend", __name__)


def login_required(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not session:
            return await flash(
                "error",
                "You must be logged in to access that page.",
                "login",
            )
        return await func(*args, **kwargs)

    return wrapper


@frontend.route("/home")
@frontend.route("/")
async def home():
    return await render_template("home.html")


@frontend.route("/home/account/edit")
async def home_account_edit():
    return redirect("/settings/profile")


@frontend.route("/settings")
@frontend.route("/settings/profile")
@login_required
async def settings_profile():
    return await render_template("settings/profile.html")


@frontend.route("/settings/profile", methods=["POST"])
@login_required
async def settings_profile_post():
    form = await request.form

    new_name = form.get("username", type=str)
    new_email = form.get("email", type=str)

    if new_name is None or new_email is None:
        return await flash("error", "Invalid parameters.", "home")

    old_name = session["user_data"]["name"]
    old_email = session["user_data"]["email"]

    # no data has changed; deny post
    if new_name == old_name and new_email == old_email:
        return await flash("error", "No changes have been made.", "settings/profile")

    if new_name != old_name:
        if not session["user_data"]["is_donator"]:
            return await flash(
                "error",
                "Username changes are currently a supporter perk.",
                "settings/profile",
            )

        # Usernames must:
        # - be within 2-15 characters in length
        # - not contain both ' ' and '_', one is fine
        # - not be in the config's `disallowed_names` list
        # - not already be taken by another player
        if not regexes.username.match(new_name):
            return await flash(
                "error",
                "Your new username syntax is invalid.",
                "settings/profile",
            )

        if "_" in new_name and " " in new_name:
            return await flash(
                "error",
                'Your new username may contain "_" or " ", but not both.',
                "settings/profile",
            )

        if new_name in common.settings.DISALLOWED_USERNAMES:
            return await flash(
                "error",
                "Your new username isn't allowed; pick another.",
                "settings/profile",
            )

        if await state.clients.database.fetch_one(
            "SELECT 1 FROM users WHERE name = :name",
            {"name": new_name},
        ):
            return await flash(
                "error",
                "Your new username already taken by another user.",
                "settings/profile",
            )

        safe_name = utils.get_safe_name(new_name)

        # username change successful
        await state.clients.database.execute(
            "UPDATE users "
            "SET name = :name, safe_name = :safe_name "
            "WHERE id = :id",
            {
                "name": new_name,
                "safe_name": safe_name,
                "id": session["user_data"]["id"],
            },
        )

    if new_email != old_email:
        # Emails must:
        # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
        # - not already be taken by another player
        if not regexes.email.match(new_email):
            return await flash(
                "error",
                "Your new email syntax is invalid.",
                "settings/profile",
            )

        if await state.clients.database.fetch_one(
            "SELECT 1 FROM users WHERE email = :email",
            {"email": new_email},
        ):
            return await flash(
                "error",
                "Your new email already taken by another user.",
                "settings/profile",
            )

        # email change successful
        await state.clients.database.execute(
            "UPDATE users " "SET email = :email " "WHERE id = :id",
            {"email": new_email, "id": session["user_data"]["id"]},
        )

    # logout
    session.pop("authenticated", None)
    session.pop("user_data", None)
    return await flash(
        "success",
        "Your username/email have been changed! Please login again.",
        "login",
    )


@frontend.route("/settings/avatar")
@login_required
async def settings_avatar():
    return await render_template("settings/avatar.html")


@frontend.route("/settings/avatar", methods=["POST"])
@login_required
async def settings_avatar_post():
    # constants
    MAX_IMAGE_SIZE = common.settings.MAX_IMAGE_SIZE * 1024 * 1024
    AVATARS_PATH = f"{common.settings.PATH_TO_BPY}.data/avatars"
    ALLOWED_EXTENSIONS = [".jpeg", ".jpg", ".png"]

    avatar = (await request.files).get("avatar")

    # no file uploaded; deny post
    if avatar is None or not avatar.filename:
        return await flash("error", "No image was selected!", "settings/avatar")

    filename, file_extension = os.path.splitext(avatar.filename.lower())

    # bad file extension; deny post
    if not file_extension in ALLOWED_EXTENSIONS:
        return await flash(
            "error",
            "The image you select must be either a .JPG, .JPEG, or .PNG file!",
            "settings/avatar",
        )

    # check file size of avatar
    if avatar.content_length > MAX_IMAGE_SIZE:
        return await flash(
            "error",
            "The image you selected is too large!",
            "settings/avatar",
        )

    # remove old avatars
    for fx in ALLOWED_EXTENSIONS:
        if os.path.isfile(
            f'{AVATARS_PATH}/{session["user_data"]["id"]}{fx}',
        ):  # Checking file e
            os.remove(f'{AVATARS_PATH}/{session["user_data"]["id"]}{fx}')

    # avatar cropping to 1:1
    pilavatar = Image.open(avatar.stream)

    # avatar change success
    pilavatar = utils.crop_image(pilavatar)
    pilavatar.save(
        os.path.join(
            AVATARS_PATH,
            f'{session["user_data"]["id"]}{file_extension.lower()}',
        ),
    )
    return await flash(
        "success",
        "Your avatar has been successfully changed!",
        "settings/avatar",
    )


@frontend.route("/settings/custom")
@login_required
async def settings_custom():
    profile_customizations = utils.has_profile_customizations(
        session["user_data"]["id"],
    )
    return await render_template(
        "settings/custom.html",
        customizations=profile_customizations,
    )


@frontend.route("/settings/custom", methods=["POST"])
@login_required
async def settings_custom_post():
    files = await request.files
    banner = files.get("banner")
    background = files.get("background")
    ALLOWED_EXTENSIONS = [".jpeg", ".jpg", ".png", ".gif"]

    # no file uploaded; deny post
    if banner is None and background is None:
        return await flash_with_customizations(
            "error",
            "No image was selected!",
            "settings/custom",
        )

    if banner is not None and banner.filename:
        _, file_extension = os.path.splitext(banner.filename.lower())
        if not file_extension in ALLOWED_EXTENSIONS:
            return await flash_with_customizations(
                "error",
                f"The banner you select must be either a .JPG, .JPEG, .PNG or .GIF file!",
                "settings/custom",
            )

        banner_file_no_ext = os.path.join(
            f".data/banners",
            f'{session["user_data"]["id"]}',
        )

        # remove old picture
        for ext in ALLOWED_EXTENSIONS:
            banner_file_with_ext = f"{banner_file_no_ext}{ext}"
            if os.path.isfile(banner_file_with_ext):
                os.remove(banner_file_with_ext)

        await banner.save(f"{banner_file_no_ext}{file_extension}")

    if background is not None and background.filename:
        _, file_extension = os.path.splitext(background.filename.lower())
        if not file_extension in ALLOWED_EXTENSIONS:
            return await flash_with_customizations(
                "error",
                f"The background you select must be either a .JPG, .JPEG, .PNG or .GIF file!",
                "settings/custom",
            )

        background_file_no_ext = os.path.join(
            f".data/backgrounds",
            f'{session["user_data"]["id"]}',
        )

        # remove old picture
        for ext in ALLOWED_EXTENSIONS:
            background_file_with_ext = f"{background_file_no_ext}{ext}"
            if os.path.isfile(background_file_with_ext):
                os.remove(background_file_with_ext)

        await background.save(f"{background_file_no_ext}{file_extension}")

    return await flash_with_customizations(
        "success",
        "Your customisation has been successfully changed!",
        "settings/custom",
    )


@frontend.route("/settings/password")
@login_required
async def settings_password():
    return await render_template("settings/password.html")


@frontend.route("/settings/password", methods=["POST"])
@login_required
async def settings_password_post():
    form = await request.form
    old_password = form.get("old_password")
    new_password = form.get("new_password")
    repeat_password = form.get("repeat_password")

    assert old_password is not None
    assert new_password is not None
    assert repeat_password is not None

    # new password and repeat password don't match; deny post
    if new_password != repeat_password:
        return await flash(
            "error",
            "Your new password doesn't match your repeated password!",
            "settings/password",
        )

    # new password and old password match; deny post
    if old_password == new_password:
        return await flash(
            "error",
            "Your new password cannot be the same as your old password!",
            "settings/password",
        )

    # Passwords must:
    # - be within 8-32 characters in length
    # - have more than 3 unique characters
    # - not be in the config's `disallowed_passwords` list
    if not 8 < len(new_password) <= 32:
        return await flash(
            "error",
            "Your new password must be 8-32 characters in length.",
            "settings/password",
        )

    if len(set(new_password)) <= 3:
        return await flash(
            "error",
            "Your new password must have more than 3 unique characters.",
            "settings/password",
        )

    if new_password.lower() in common.settings.DISALLOWED_PASSWORDS:
        return await flash(
            "error",
            "Your new password was deemed too simple.",
            "settings/password",
        )

    # cache and other password related information
    bcrypt_cache = state.cache.bcrypt
    pw_bcrypt = await state.clients.database.fetch_one(
        "SELECT pw_bcrypt " "FROM users " "WHERE id = :id",
        {"id": session["user_data"]["id"]},
    )

    assert pw_bcrypt is not None

    pw_bcrypt = pw_bcrypt["pw_bcrypt"].encode()

    pw_md5 = hashlib.md5(old_password.encode()).hexdigest().encode()

    # check old password against db
    # intentionally slow, will cache to speed up
    if pw_bcrypt in bcrypt_cache:
        if pw_md5 != bcrypt_cache[pw_bcrypt]:  # ~0.1ms
            if common.settings.DEBUG:
                log(
                    f"{session['user_data']['name']}'s change pw failed - pw incorrect.",
                    Ansi.LYELLOW,
                )
            return await flash(
                "error",
                "Your old password is incorrect.",
                "settings/password",
            )
    else:  # ~200ms
        if not bcrypt.checkpw(pw_md5, pw_bcrypt):
            if common.settings.DEBUG:
                log(
                    f"{session['user_data']['name']}'s change pw failed - pw incorrect.",
                    Ansi.LYELLOW,
                )
            return await flash(
                "error",
                "Your old password is incorrect.",
                "settings/password",
            )

    # remove old password from cache
    if pw_bcrypt in bcrypt_cache:
        del bcrypt_cache[pw_bcrypt]

    # calculate new md5 & bcrypt pw
    pw_md5 = hashlib.md5(new_password.encode()).hexdigest().encode()
    pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())

    # update password in cache and db
    bcrypt_cache[pw_bcrypt] = pw_md5
    await state.clients.database.execute(
        "UPDATE users " "SET pw_bcrypt = :pw_bcrypt " "WHERE safe_name = :safe_name",
        {
            "pw_bcrypt": pw_bcrypt,
            "safe_name": utils.get_safe_name(session["user_data"]["name"]),
        },
    )

    # logout
    session.pop("authenticated", None)
    session.pop("user_data", None)
    return await flash(
        "success",
        "Your password has been changed! Please log in again.",
        "login",
    )


@frontend.route("/u/<id>")
async def profile_select(id):

    mode = request.args.get("mode", "std", type=str)  # 1. key 2. default value
    mods = request.args.get("mods", "vn", type=str)
    user_data = await state.clients.database.fetch_one(
        "SELECT name, safe_name, id, priv, country "
        "FROM users "
        "WHERE safe_name = :safe_name OR id = :id LIMIT 1",
        {"safe_name": utils.get_safe_name(id), "id": id},
    )

    # no user
    if not user_data:
        return (await render_template("404.html"), 404)

    # make sure mode & mods are valid args
    if mode is not None and mode not in VALID_MODES:
        return (await render_template("404.html"), 404)

    if mods is not None and mods not in VALID_MODS:
        return (await render_template("404.html"), 404)

    is_staff = "authenticated" in session and session["user_data"]["is_staff"]
    if not user_data or not (user_data["priv"] & Privileges.Normal or is_staff):
        return (await render_template("404.html"), 404)

    user_data["customisation"] = utils.has_profile_customizations(user_data["id"])
    return await render_template("profile.html", user=user_data, mode=mode, mods=mods)


@frontend.route("/leaderboard")
@frontend.route("/lb")
@frontend.route("/leaderboard/<mode>/<sort>/<mods>")
@frontend.route("/lb/<mode>/<sort>/<mods>")
async def leaderboard(mode="std", sort="pp", mods="vn"):
    return await render_template("leaderboard.html", mode=mode, sort=sort, mods=mods)


@frontend.route("/login")
async def login():
    if "authenticated" in session:
        return await flash("error", "You're already logged in!", "home")

    return await render_template("login.html")


@frontend.route("/login", methods=["POST"])
async def login_post():
    if "authenticated" in session:
        return await flash("error", "You're already logged in!", "home")

    if common.settings.DEBUG:
        login_time = time.time_ns()

    form = await request.form
    username = form.get("username", type=str)
    passwd_txt = form.get("password", type=str)

    if username is None or passwd_txt is None:
        return await flash("error", "Invalid parameters.", "home")

    # check if account exists
    user_info = await state.clients.database.fetch_one(
        "SELECT id, name, email, priv, "
        "pw_bcrypt, silence_end "
        "FROM users "
        "WHERE safe_name = :safe_name",
        {"safe_name": utils.get_safe_name(username)},
    )

    # user doesn't exist; deny post
    # NOTE: Bot isn't a user.
    if not user_info or user_info["id"] == 1:
        if common.settings.DEBUG:
            log(f"{username}'s login failed - account doesn't exist.", Ansi.LYELLOW)
        return await flash("error", "Account does not exist.", "login")

    # cache and other related password information
    bcrypt_cache = state.cache.bcrypt
    pw_bcrypt = user_info["pw_bcrypt"].encode()
    pw_md5 = hashlib.md5(passwd_txt.encode()).hexdigest().encode()

    # check credentials (password) against db
    # intentionally slow, will cache to speed up
    if pw_bcrypt in bcrypt_cache:
        if pw_md5 != bcrypt_cache[pw_bcrypt]:  # ~0.1ms
            if common.settings.DEBUG:
                log(f"{username}'s login failed - pw incorrect.", Ansi.LYELLOW)
            return await flash("error", "Password is incorrect.", "login")
    else:  # ~200ms
        if not bcrypt.checkpw(pw_md5, pw_bcrypt):
            if common.settings.DEBUG:
                log(f"{username}'s login failed - pw incorrect.", Ansi.LYELLOW)
            return await flash("error", "Password is incorrect.", "login")

        # login successful; cache password for next login
        bcrypt_cache[pw_bcrypt] = pw_md5

    # user not verified; render verify
    if not user_info["priv"] & Privileges.Verified:
        if common.settings.DEBUG:
            log(f"{username}'s login failed - not verified.", Ansi.LYELLOW)
        return await render_template("verify.html")

    # user banned; deny post
    if not user_info["priv"] & Privileges.Normal:
        if common.settings.DEBUG:
            log(f"{username}'s login failed - banned.", Ansi.RED)
        return await flash(
            "error",
            "Your account is restricted. You are not allowed to log in.",
            "login",
        )

    # login successful; store session data
    if common.settings.DEBUG:
        log(f"{username}'s login succeeded.", Ansi.LGREEN)

    session["authenticated"] = True
    session["user_data"] = {
        "id": user_info["id"],
        "name": user_info["name"],
        "email": user_info["email"],
        "priv": user_info["priv"],
        "silence_end": user_info["silence_end"],
        "is_staff": user_info["priv"] & Privileges.Staff != 0,
        "is_donator": user_info["priv"] & Privileges.Donator != 0,
    }

    if common.settings.DEBUG:
        login_time = (time.time_ns() - login_time) / 1e6  # type: ignore
        log(f"Login took {login_time:.2f}ms!", Ansi.LYELLOW)

    return await flash("success", f"Hey, welcome back {username}!", "home")


_status_str_dict = {
    3: "Approved",
    4: "Qualified",
    2: "Ranked",
    5: "Loved",
    0: "Pending",
    -1: "Unranked",
    -2: "Graveyarded",
}

_mode_str_dict = {0: "std", 1: "taiko", 2: "catch", 3: "mania"}


@frontend.route("/b/<bid>")
@frontend.route("/beatmaps/<bid>")
async def beatmap(bid):
    mode = request.args.get("mode", "std", type=str)  # 1. key 2. default value
    mods = request.args.get("mods", "vn", type=str)

    # Make sure mode, mods and id are valid, otherwise 404 page
    if (
        bid == None
        or not bid.isdigit()
        or mode not in VALID_MODES
        or mods not in VALID_MODS
        or mode == "mania"
        and mods == "rx"
        or mods == "ap"
        and mode != "std"
    ):
        return (await render_template("404.html"), 404)

    # get the beatmap by id
    bmap = await state.clients.database.fetch_one(
        "SELECT * FROM maps WHERE id = :id",
        {"id": bid},
    )
    if not bmap:
        return (await render_template("404.html"), 404)

    # get all other difficulties
    bmapset = await state.clients.database.fetch_all(
        "SELECT diff, status, version, id, mode FROM maps WHERE set_id = :set_id ORDER BY diff",
        {"set_id": bmap["set_id"]},
    )

    # sanitize the values
    for _bmap in bmapset:
        _bmap["diff"] = round(_bmap["diff"], 2)
        _bmap["modetext"] = _mode_str_dict[_bmap["mode"]]
        _bmap["diff_color"] = utils.get_difficulty_colour_spectrum(_bmap["diff"])
        _bmap["icon"] = utils.get_mode_icon(_bmap["mode"])
        _bmap["status"] = _status_str_dict[_bmap["status"]]

    status = _status_str_dict[bmap["status"]]
    is_bancho = int(bmap["frozen"]) == 0
    return await render_template(
        "beatmap.html",
        bmap=bmap,
        bmapset=bmapset,
        status=status,
        mode=mode,
        mods=mods,
        is_bancho=is_bancho,
    )


@frontend.route("/scores/<id>")
async def score(id):
    mods_mode_strs = {
        1: ("Vanilla Taiko", "taiko", "vn"),
        2: ("Vanilla CTB", "catch", "vn"),
        3: ("Vanilla Mania", "mania", "vn"),
        4: ("Relax Standard", "std", "rx"),
        5: ("Relax Taiko", "taiko", "rx"),
        6: ("Relax Catch", "catch", "rx"),
        8: ("AutoPilot Standard", "std", "ap"),
    }

    score_data = await state.clients.database.fetch_one(
        "SELECT pp, time_elapsed, play_time, score, grade, id, nmiss, n300, n100, n50, acc, userid, mods, max_combo, mode, map_md5 FROM scores WHERE id = :id",
        {"id": id},
    )
    if not score_data:
        return await flash("error", "Score not found!", "home")

    map_data = await state.clients.database.fetch_one(
        "SELECT id, total_length, set_id, diff, title, creator, version, artist, status, max_combo FROM maps WHERE md5 = :md5",
        {"md5": score_data["map_md5"]},
    )
    if not map_data:
        return await flash("error", "Could not find the beatmap.", "home")

    user_data = await state.clients.database.fetch_one(
        "SELECT name, country FROM users WHERE id = :id",
        {"id": score_data["userid"]},
    )
    if not user_data:
        return await flash("error", "Could not find the user.", "home")

    # score converts
    score_data["acc"] = round(float(score_data["acc"]), 2)
    score_data["pp"] = round(float(score_data["pp"]), 2)
    score_data["score"] = "{:,}".format(int(score_data["score"]))
    score_data["grade"] = utils.get_color_formatted_grade(score_data["grade"])
    score_data["ptformatted"] = datetime.datetime.strptime(
        str(score_data["play_time"]),
        "%Y-%m-%d %H:%M:%S",
    ).strftime("%d %B %Y %H:%M:%S")
    if score_data["mods"] != 0:
        score_data["mods"] = utils.get_mods(score_data["mods"])
    score_data["mode_icon"] = utils.get_mode_icon(score_data["mode"])
    mods_mode_str, mode, mods = mods_mode_strs.get(
        score_data["mode"],
        ("Vanilla Standard", "std", "vn"),
    )

    if score_data["grade"]["letter"] == "F":
        if map_data["total_length"] != 0:
            score_data["mapprogress"] = (
                f"{(score_data['time_elapsed'] / (map_data['total_length'] * 1000)) * 100:.2f}%"
            )
        else:
            score_data["mapprogress"] = "undefined"

    # map converts
    map_data["colordiff"] = utils.get_difficulty_colour_spectrum(map_data["diff"])
    map_data["diff"] = round(map_data["diff"], 2)

    user_data["customization"] = utils.has_profile_customizations(score_data["userid"])
    return await render_template(
        "score.html",
        score=score_data,
        mods_mode_str=mods_mode_str,
        map=map_data,
        mode=mode,
        mods=mods,
        userinfo=user_data,
        datetime=datetime,
        timeago=timeago,
        pp=int(score_data["pp"] + 0.5),
    )


@frontend.route("/register")
async def register():
    if "authenticated" in session:
        return await flash("error", "You're already logged in.", "home")

    if not common.settings.ALLOW_REGISTRATION:
        return await flash("error", "Registrations are currently disabled.", "home")

    return await render_template("register.html")


@frontend.route("/register", methods=["POST"])
async def register_post():
    if "authenticated" in session:
        return await flash("error", "You're already logged in.", "home")

    if not common.settings.ALLOW_REGISTRATION:
        return await flash("error", "Registrations are currently disabled.", "home")

    form = await request.form
    username = form.get("username", type=str)
    email = form.get("email", type=str)
    passwd_txt = form.get("password", type=str)

    if username is None or email is None or passwd_txt is None:
        return await flash("error", "Invalid parameters.", "home")

    if common.settings.HCAPTCHA_SITE_KEY != "changeme":
        captcha_data = form.get("h-captcha-response", type=str)
        if captcha_data is None or not await utils.validate_captcha(captcha_data):
            return await flash("error", "Captcha failed.", "register")

    # Usernames must:
    # - be within 2-15 characters in length
    # - not contain both ' ' and '_', one is fine
    # - not be in the config's `disallowed_names` list
    # - not already be taken by another player
    # check if username exists
    if not regexes.username.match(username):
        return await flash("error", "Invalid username syntax.", "register")

    if "_" in username and " " in username:
        return await flash(
            "error",
            'Username may contain "_" or " ", but not both.',
            "register",
        )

    if username in common.settings.DISALLOWED_USERNAMES:
        return await flash("error", "Disallowed username; pick another.", "register")

    if await state.clients.database.fetch_one(
        "SELECT 1 FROM users WHERE name = :name",
        {"name": username},
    ):
        return await flash(
            "error",
            "Username already taken by another user.",
            "register",
        )

    # Emails must:
    # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
    # - not already be taken by another player
    if not regexes.email.match(email):
        return await flash("error", "Invalid email syntax.", "register")

    if await state.clients.database.fetch_one(
        "SELECT 1 FROM users WHERE email = :email",
        {"email": email},
    ):
        return await flash("error", "Email already taken by another user.", "register")

    # Passwords must:
    # - be within 8-32 characters in length
    # - have more than 3 unique characters
    # - not be in the config's `disallowed_passwords` list
    if not 8 <= len(passwd_txt) <= 32:
        return await flash(
            "error",
            "Password must be 8-32 characters in length.",
            "register",
        )

    if len(set(passwd_txt)) <= 3:
        return await flash(
            "error",
            "Password must have more than 3 unique characters.",
            "register",
        )

    if passwd_txt.lower() in common.settings.DISALLOWED_PASSWORDS:
        return await flash("error", "That password was deemed too simple.", "register")

    # TODO: add correct locking
    # (start of lock)
    pw_md5 = hashlib.md5(passwd_txt.encode()).hexdigest().encode()
    pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())
    state.cache.bcrypt[pw_bcrypt] = pw_md5  # cache pw

    safe_name = utils.get_safe_name(username)

    # fetch the users' country
    if (
        request.headers
        and (ip := request.headers.get("X-Real-IP", type=str)) is not None
    ):
        country = await utils.fetch_geoloc(ip)
    else:
        country = "xx"

    if country != "pe":
        return await flash("error", "You must be in Peru to register.", "register")

    async with state.clients.database.transaction():
        # add to `users` table.
        user_id = await state.clients.database.execute(
            "INSERT INTO users "
            "(name, safe_name, email, pw_bcrypt, country, creation_time, latest_activity) "
            "VALUES (:username, :safe_name, :email, :pw_bcrypt, :country, UNIX_TIMESTAMP(), UNIX_TIMESTAMP())",
            {
                "username": username,
                "safe_name": safe_name,
                "email": email,
                "pw_bcrypt": pw_bcrypt,
                "country": country,
            },
        )

        await state.clients.database.execute_many(
            "INSERT INTO stats (id, mode) VALUES (:id, :mode)",
            [
                {"id": user_id, "mode": mode}
                for mode in (
                    0,  # vn!std
                    1,  # vn!taiko
                    2,  # vn!catch
                    3,  # vn!mania
                    4,  # rx!std
                    5,  # rx!taiko
                    6,  # rx!catch
                    8,  # ap!std
                )
            ],
        )

    # (end of lock)

    if common.settings.DEBUG:
        log(f"{username} has registered - awaiting verification.", Ansi.LGREEN)

    # user has successfully registered
    return await render_template("verify.html")


@frontend.route("/logout")
async def logout():
    if "authenticated" not in session:
        return await flash(
            "error",
            "You can't logout if you aren't logged in!",
            "login",
        )

    if common.settings.DEBUG:
        log(f'{session["user_data"]["name"]} logged out.', Ansi.LGREEN)

    # clear session data
    session.pop("authenticated", None)
    session.pop("user_data", None)

    # render login
    return await flash("success", "Successfully logged out!", "login")


# social media redirections


@frontend.route("/github")
@frontend.route("/gh")
async def github_redirect():
    return redirect(common.settings.GITHUB)


@frontend.route("/discord")
async def discord_redirect():
    return redirect(common.settings.DISCORD_SERVER)


@frontend.route("/youtube")
@frontend.route("/yt")
async def youtube_redirect():
    return redirect(common.settings.YOUTUBE)


@frontend.route("/twitter")
async def twitter_redirect():
    return redirect(common.settings.TWITTER)


@frontend.route("/instagram")
@frontend.route("/ig")
async def instagram_redirect():
    return redirect(common.settings.INSTAGRAM)


# profile customisation
BANNERS_PATH = Path.cwd() / ".data/banners"
BACKGROUND_PATH = Path.cwd() / ".data/backgrounds"


@frontend.route("/banners/<user_id>")
async def get_profile_banner(user_id: int):
    # Check if avatar exists
    for ext in ("jpg", "jpeg", "png", "gif"):
        path = BANNERS_PATH / f"{user_id}.{ext}"
        if path.exists():
            return await send_file(path)

    return b'{"status":404}'


@frontend.route("/backgrounds/<user_id>")
async def get_profile_background(user_id: int):
    # Check if avatar exists
    for ext in ("jpg", "jpeg", "png", "gif"):
        path = BACKGROUND_PATH / f"{user_id}.{ext}"
        if path.exists():
            return await send_file(path)

    return b'{"status":404}'
