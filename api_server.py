import os
import json
import asyncio
import threading
from pathlib import Path
from datetime import timedelta

import requests
from flask import Flask, request, redirect, session, jsonify, send_from_directory

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(__file__).parent.parent  # racine du projet, là où vivent badges.json etc.

app = Flask(__name__, static_folder=str(BASE_DIR / "static"))
app.secret_key = os.getenv("SESSION_SECRET", "change-moi-en-prod")

# Sans ça, Flask traite le cookie de session comme un "cookie de session" classique,
# que certains navigateurs (Chrome mobile en particulier) suppriment très vite quand
# l'onglet passe en arrière-plan. On le rend permanent pour que la connexion tienne.
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True  # le site tourne en HTTPS sur Railway

DISCORD_API = "https://discord.com/api"
ADMINISTRATOR = 0x8

# Rempli par main.py au démarrage : référence vers l'instance du bot discord.py,
# pour qu'on puisse lire ses serveurs/salons/rôles en cache sans requête HTTP en plus.
_bot = None


def set_bot(bot_instance):
    global _bot
    _bot = bot_instance


def run_bot_coroutine(coro, timeout=10):
    """Exécute une coroutine discord.py (ex: envoyer un message) depuis Flask,
    qui tourne dans un thread séparé de la boucle asyncio du bot."""
    if not _bot:
        raise RuntimeError("Le bot n'est pas encore prêt")
    future = asyncio.run_coroutine_threadsafe(coro, _bot.loop)
    return future.result(timeout=timeout)


# ---------- Fichiers de données partagés avec le bot ----------
def load_json(filename, default):
    path = DATA_DIR / filename
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filename, data):
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------- Auth helpers ----------
def get_admin_guild_ids():
    """Guilds où l'utilisateur connecté a la permission Administrateur
    (déjà filtrées lors de la connexion, voir /callback)."""
    return {g["id"] for g in session.get("guilds", [])}


def require_login():
    return "user" in session


def require_guild_admin(guild_id: str) -> bool:
    if not require_login():
        return False
    return guild_id in get_admin_guild_ids()


# ---------- Pages ----------
@app.route("/")
def home():
    return send_from_directory(app.static_folder, "dashboard.html")


# ---------- OAuth2 Discord ----------
@app.route("/login")
def login():
    client_id = os.getenv("DISCORD_CLIENT_ID")
    redirect_uri = os.getenv("DISCORD_REDIRECT_URI")  # ex: https://ton-repl.repl.co/callback
    scope = "identify guilds"
    url = (
        f"{DISCORD_API}/oauth2/authorize"
        f"?client_id={client_id}&redirect_uri={redirect_uri}"
        f"&response_type=code&scope={scope.replace(' ', '%20')}"
    )
    return redirect(url)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Connexion refusée ou annulée.", 400

    data = {
        "client_id": os.getenv("DISCORD_CLIENT_ID"),
        "client_secret": os.getenv("DISCORD_CLIENT_SECRET"),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": os.getenv("DISCORD_REDIRECT_URI"),
    }
    token_resp = requests.post(f"{DISCORD_API}/oauth2/token", data=data)
    if token_resp.status_code != 200:
        return f"Erreur d'échange du token : {token_resp.text}", 400
    access_token = token_resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    user = requests.get(f"{DISCORD_API}/users/@me", headers=headers).json()
    raw_guilds = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=headers).json()

    # Discord renvoie énormément de champs par serveur (features, owner, approximate_member_count...).
    # Le cookie de session est limité à ~4 Ko par les navigateurs : on ne garde que les serveurs où
    # l'utilisateur est administrateur (le seul cas qui nous intéresse), avec le strict minimum de champs.
    admin_guilds = [
        {"id": g["id"], "name": g["name"], "icon": g.get("icon")}
        for g in raw_guilds
        if (int(g["permissions"]) & ADMINISTRATOR) == ADMINISTRATOR
    ]

    session.permanent = True
    session["user"] = {"id": user["id"], "username": user["username"], "avatar": user.get("avatar")}
    session["guilds"] = admin_guilds

    return redirect("/")


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


# ---------- API : identité + serveurs administrables ----------
@app.route("/api/me")
def me():
    if not require_login():
        return jsonify({"logged_in": False})

    admin_ids = get_admin_guild_ids()
    bot_guild_ids = {str(g.id) for g in _bot.guilds} if _bot else set()

    # On ne montre que les serveurs où : le bot est présent ET l'utilisateur est admin
    usable_guild_ids = admin_ids & bot_guild_ids
    guilds_info = []
    for g in session.get("guilds", []):
        if g["id"] in usable_guild_ids:
            guilds_info.append({
                "id": g["id"],
                "name": g["name"],
                "icon": g.get("icon"),
            })

    return jsonify({
        "logged_in": True,
        "user": {
            "id": session["user"]["id"],
            "username": session["user"]["username"],
            "avatar": session["user"].get("avatar"),
        },
        "guilds": guilds_info,
    })


# ---------- API : salons / rôles réels d'un serveur ----------
@app.route("/api/guilds/<guild_id>/channels")
def guild_channels(guild_id):
    if not require_guild_admin(guild_id):
        return jsonify({"error": "forbidden"}), 403
    if not _bot:
        return jsonify({"error": "bot indisponible"}), 503

    guild = _bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"error": "le bot n'est pas sur ce serveur"}), 404

    return jsonify({
        "text_channels": [{"id": str(c.id), "name": c.name} for c in guild.text_channels],
        "voice_channels": [{"id": str(c.id), "name": c.name} for c in guild.voice_channels],
        "roles": [{"id": str(r.id), "name": r.name} for r in guild.roles if r.name != "@everyone"],
        "categories": [{"id": str(c.id), "name": c.name} for c in guild.categories],
    })


# ---------- API : notifications sociales (même fichier que le cog social_alerts) ----------
@app.route("/api/guilds/<guild_id>/social", methods=["GET", "POST", "DELETE"])
def guild_social(guild_id):
    if not require_guild_admin(guild_id):
        return jsonify({"error": "forbidden"}), 403

    alerts = load_json("social_alerts.json", {})
    guild_alerts = alerts.get(guild_id, [])

    if request.method == "GET":
        return jsonify(guild_alerts)

    if request.method == "POST":
        body = request.get_json()
        entry = {
            "platform": body["platform"],
            "link": body["link"],
            "channel_id": int(body["channel_id"]),
        }
        if body["platform"] == "youtube":
            entry["last_video_id"] = None
        elif body["platform"] == "tiktok":
            entry["last_video_id"] = None
        else:
            entry["was_live"] = False
        guild_alerts.append(entry)
        alerts[guild_id] = guild_alerts
        save_json("social_alerts.json", alerts)
        return jsonify({"ok": True, "alerts": guild_alerts})

    if request.method == "DELETE":
        index = int(request.args.get("index", -1))
        if 0 <= index < len(guild_alerts):
            guild_alerts.pop(index)
            alerts[guild_id] = guild_alerts
            save_json("social_alerts.json", alerts)
        return jsonify({"ok": True, "alerts": guild_alerts})


# ---------- API : modération (toggles simples, stockés à part) ----------
@app.route("/api/guilds/<guild_id>/moderation", methods=["GET", "POST"])
def guild_moderation(guild_id):
    if not require_guild_admin(guild_id):
        return jsonify({"error": "forbidden"}), 403

    config = load_json("moderation_config.json", {})
    guild_config = config.get(guild_id, {
        "anti_spam": True,
        "anti_link": True,
        "anti_raid": False,
        "log_channel_id": None,
    })

    if request.method == "GET":
        return jsonify(guild_config)

    body = request.get_json()
    guild_config.update(body)
    config[guild_id] = guild_config
    save_json("moderation_config.json", config)
    return jsonify({"ok": True, "config": guild_config})


# ---------- API : messages de bienvenue / au revoir ----------
@app.route("/api/guilds/<guild_id>/welcome", methods=["GET", "POST"])
def guild_welcome(guild_id):
    if not require_guild_admin(guild_id):
        return jsonify({"error": "forbidden"}), 403

    config = load_json("welcome_config.json", {})
    guild_config = config.get(guild_id, {
        "welcome_enabled": True,
        "goodbye_enabled": False,
        "channel_id": None,
        "welcome_message": "Bienvenue {membre} sur le serveur ! 🎉",
        "goodbye_message": "{membre} a quitté le serveur.",
    })

    if request.method == "GET":
        return jsonify(guild_config)

    body = request.get_json()
    guild_config.update(body)
    config[guild_id] = guild_config
    save_json("welcome_config.json", config)
    return jsonify({"ok": True, "config": guild_config})


# ---------- API : rôles à la réaction ----------
@app.route("/api/guilds/<guild_id>/reaction-roles", methods=["GET", "POST", "DELETE"])
def guild_reaction_roles(guild_id):
    if not require_guild_admin(guild_id):
        return jsonify({"error": "forbidden"}), 403

    data = load_json("reaction_roles.json", {})
    entries = data.get(guild_id, [])

    if request.method == "GET":
        return jsonify(entries)

    if request.method == "DELETE":
        index = int(request.args.get("index", -1))
        if 0 <= index < len(entries):
            entries.pop(index)
            data[guild_id] = entries
            save_json("reaction_roles.json", data)
        return jsonify({"ok": True, "entries": entries})

    # POST : envoie réellement le message sur Discord, avec la réaction posée dessus
    body = request.get_json()
    channel_id = int(body["channel_id"])
    role_id = int(body["role_id"])
    emoji = body["emoji"]
    message_text = body.get("message") or "Réagis pour obtenir le rôle !"

    if not _bot:
        return jsonify({"error": "bot indisponible"}), 503
    guild = _bot.get_guild(int(guild_id))
    channel = guild.get_channel(channel_id) if guild else None
    role = guild.get_role(role_id) if guild else None
    if not channel or not role:
        return jsonify({"error": "salon ou rôle introuvable"}), 404

    async def send_and_react():
        import discord
        embed = discord.Embed(
            title="🎭 Rôle à la réaction",
            description=message_text,
            color=discord.Color.blue(),
        )
        msg = await channel.send(embed=embed)
        await msg.add_reaction(emoji)
        return msg.id

    try:
        message_id = run_bot_coroutine(send_and_react())
    except Exception as e:
        return jsonify({"error": f"échec de l'envoi : {e}"}), 500

    entries.append({
        "message_id": message_id,
        "channel_id": channel_id,
        "role_id": role_id,
        "emoji": emoji,
        "message": message_text,
    })
    data[guild_id] = entries
    save_json("reaction_roles.json", data)
    return jsonify({"ok": True, "entries": entries})


# ---------- API : panneau de tickets ----------
@app.route("/api/guilds/<guild_id>/tickets/setup", methods=["POST"])
def guild_tickets_setup(guild_id):
    if not require_guild_admin(guild_id):
        return jsonify({"error": "forbidden"}), 403
    if not _bot:
        return jsonify({"error": "bot indisponible"}), 503

    body = request.get_json()
    channel_id = int(body["channel_id"])
    guild = _bot.get_guild(int(guild_id))
    channel = guild.get_channel(channel_id) if guild else None
    if not channel:
        return jsonify({"error": "salon introuvable"}), 404

    async def send_panel():
        import discord
        from cogs.tickets import TicketButton
        embed = discord.Embed(
            title="🎫 Support",
            description="Clique sur le bouton ci-dessous pour ouvrir un ticket privé avec le staff.",
            color=discord.Color.blurple(),
        )
        await channel.send(embed=embed, view=TicketButton())

    try:
        run_bot_coroutine(send_panel())
    except Exception as e:
        return jsonify({"error": f"échec de l'envoi : {e}"}), 500

    return jsonify({"ok": True})


# ---------- API : badges (même fichier que le cog badges) ----------
@app.route("/api/guilds/<guild_id>/badges")
def guild_badges(guild_id):
    if not require_guild_admin(guild_id):
        return jsonify({"error": "forbidden"}), 403
    badges = load_json("badges.json", {})
    guild_badges_map = badges.get(guild_id, {})

    members_info = []
    if _bot:
        guild = _bot.get_guild(int(guild_id))
        if guild:
            for uid, emoji in guild_badges_map.items():
                member = guild.get_member(int(uid))
                members_info.append({
                    "user_id": uid,
                    "username": str(member) if member else "Membre inconnu",
                    "emoji": emoji,
                })
    return jsonify(members_info)


def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def start_webapp(bot_instance):
    """À appeler depuis main.py une fois le bot créé, avant bot.start()."""
    set_bot(bot_instance)
    t = threading.Thread(target=run, daemon=True)
    t.start()
