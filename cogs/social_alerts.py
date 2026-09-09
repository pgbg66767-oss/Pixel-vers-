import os
import re
import json
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

DATA_FILE = "social_alerts.json"
CHECK_INTERVAL_MINUTES = 5


def load_alerts():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_alerts(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_twitch_username(link: str) -> str:
    """Extrait 'monstream' depuis https://twitch.tv/monstream ou juste 'monstream'."""
    link = link.strip().rstrip("/")
    match = re.search(r"twitch\.tv/([A-Za-z0-9_]+)", link)
    return match.group(1) if match else link


def extract_tiktok_username(link: str) -> str:
    """Extrait 'code3d' depuis https://www.tiktok.com/@code3d ou @code3d ou juste code3d."""
    link = link.strip().rstrip("/")
    match = re.search(r"tiktok\.com/@([\w.\-]+)", link)
    if match:
        return match.group(1)
    return link.lstrip("@")


class SocialAlerts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.alerts = load_alerts()  # { "guild_id": [ {platform, link, channel_id, last_video_id/last_live} ] }
        self.session: aiohttp.ClientSession | None = None
        self._twitch_token = None
        self.check_loop.start()

    def cog_unload(self):
        self.check_loop.cancel()

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    # ---------- Résolution des identifiants ----------
    async def resolve_youtube_channel_id(self, link: str) -> str | None:
        """Accepte un lien /channel/UC..., /@handle, ou directement un ID UC...
        Doit faire une requête pour retrouver l'ID exact si on a un @handle."""
        link = link.strip()
        direct = re.search(r"channel/(UC[\w-]+)", link)
        if direct:
            return direct.group(1)
        if link.startswith("UC") and len(link) > 10:
            return link

        # cas @handle ou nom de chaîne : on va chercher l'ID dans la page HTML publique.
        # Sans un User-Agent de vrai navigateur, YouTube renvoie une page différente
        # qui ne contient pas l'ID de la chaîne, et la détection échoue silencieusement.
        session = await self.get_session()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        }
        try:
            async with session.get(link, headers=headers, timeout=10) as resp:
                html = await resp.text()
                match = re.search(r'"channelId":"(UC[\w-]+)"', html)
                if match:
                    return match.group(1)
                # Repli : certains formats de page utilisent cette autre clé
                match2 = re.search(r'<link itemprop="url" href="[^"]*?/channel/(UC[\w-]+)"', html)
                if match2:
                    return match2.group(1)
        except Exception:
            return None
        return None

    async def get_twitch_token(self) -> str | None:
        client_id = os.getenv("TWITCH_CLIENT_ID")
        client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        if not client_id or not client_secret:
            return None
        session = await self.get_session()
        async with session.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
        ) as resp:
            data = await resp.json()
            return data.get("access_token")

    # ---------- Commandes slash ----------
    social_group = app_commands.Group(name="social", description="Gère les alertes YouTube / Twitch")

    @social_group.command(name="add", description="Ajoute une alerte YouTube ou Twitch")
    @app_commands.describe(plateforme="youtube ou twitch", lien="Lien de la chaîne", salon="Salon où publier l'annonce")
    @app_commands.choices(plateforme=[
        app_commands.Choice(name="YouTube", value="youtube"),
        app_commands.Choice(name="Twitch", value="twitch"),
        app_commands.Choice(name="TikTok", value="tiktok"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add(self, interaction: discord.Interaction, plateforme: app_commands.Choice[str], lien: str, salon: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild.id)
        self.alerts.setdefault(gid, [])

        entry = {"platform": plateforme.value, "link": lien, "channel_id": salon.id}

        if plateforme.value == "youtube":
            yt_id = await self.resolve_youtube_channel_id(lien)
            if not yt_id:
                await interaction.followup.send(
                    "❌ Impossible de trouver cette chaîne YouTube. Vérifie le lien (idéalement au format "
                    "`https://www.youtube.com/channel/UC...`).", ephemeral=True
                )
                return
            entry["youtube_channel_id"] = yt_id
            entry["last_video_id"] = None
        elif plateforme.value == "twitch":
            entry["twitch_username"] = extract_twitch_username(lien)
            entry["was_live"] = False
        else:  # tiktok
            entry["tiktok_username"] = extract_tiktok_username(lien)
            entry["last_video_id"] = None

        self.alerts[gid].append(entry)
        save_alerts(self.alerts)
        await interaction.followup.send(
            f"✅ Alerte **{plateforme.name}** ajoutée pour {lien} → {salon.mention}", ephemeral=True
        )

    @social_group.command(name="list", description="Liste les alertes configurées sur ce serveur")
    async def list_alerts(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        entries = self.alerts.get(gid, [])
        if not entries:
            await interaction.response.send_message("Aucune alerte configurée.", ephemeral=True)
            return
        lines = []
        for i, e in enumerate(entries):
            channel = interaction.guild.get_channel(e["channel_id"])
            chan_mention = channel.mention if channel else "salon supprimé"
            lines.append(f"`{i}` — **{e['platform']}** — {e['link']} → {chan_mention}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @social_group.command(name="remove", description="Retire une alerte (utilise l'index donné par /social list)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove(self, interaction: discord.Interaction, index: int):
        gid = str(interaction.guild.id)
        entries = self.alerts.get(gid, [])
        if index < 0 or index >= len(entries):
            await interaction.response.send_message("Index invalide. Utilise `/social list` pour voir les index.", ephemeral=True)
            return
        removed = entries.pop(index)
        save_alerts(self.alerts)
        await interaction.response.send_message(f"🗑️ Alerte retirée : {removed['link']}", ephemeral=True)

    # ---------- Vérification périodique ----------
    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def check_loop(self):
        for gid, entries in list(self.alerts.items()):
            guild = self.bot.get_guild(int(gid))
            if not guild:
                continue
            for entry in entries:
                try:
                    if entry["platform"] == "youtube":
                        await self._check_youtube(guild, entry)
                    elif entry["platform"] == "twitch":
                        await self._check_twitch(guild, entry)
                    else:
                        await self._check_tiktok(guild, entry)
                except Exception as e:
                    print(f"⚠️ Erreur vérification alerte sociale ({entry['link']}) : {e}")
        save_alerts(self.alerts)

    @check_loop.before_loop
    async def before_check_loop(self):
        await self.bot.wait_until_ready()

    async def _check_youtube(self, guild: discord.Guild, entry: dict):
        yt_id = entry.get("youtube_channel_id")
        if not yt_id:
            return
        session = await self.get_session()
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={yt_id}"
        async with session.get(feed_url, timeout=10) as resp:
            if resp.status != 200:
                return
            xml = await resp.text()

        video_id_match = re.search(r"<yt:videoId>([\w-]+)</yt:videoId>", xml)
        # Récupère le titre de la 1ère entrée (le flux liste les vidéos les plus récentes en premier)
        entries_titles = re.findall(r"<title>([^<]+)</title>", xml)
        latest_title = entries_titles[1] if len(entries_titles) > 1 else "Nouvelle vidéo"

        if not video_id_match:
            return
        latest_id = video_id_match.group(1)

        if entry.get("last_video_id") is None:
            # première vérification : on mémorise sans annoncer, pour éviter de spammer l'historique
            entry["last_video_id"] = latest_id
            return

        if latest_id != entry["last_video_id"]:
            entry["last_video_id"] = latest_id
            channel = guild.get_channel(entry["channel_id"])
            if channel:
                await channel.send(
                    f"🔴 Nouvelle vidéo YouTube : **{latest_title}**\nhttps://www.youtube.com/watch?v={latest_id}"
                )

    async def _check_twitch(self, guild: discord.Guild, entry: dict):
        username = entry.get("twitch_username")
        if not username:
            return
        if self._twitch_token is None:
            self._twitch_token = await self.get_twitch_token()
        if self._twitch_token is None:
            return  # secrets Twitch non configurés

        session = await self.get_session()
        headers = {
            "Client-ID": os.getenv("TWITCH_CLIENT_ID"),
            "Authorization": f"Bearer {self._twitch_token}",
        }
        async with session.get(
            "https://api.twitch.tv/helix/streams",
            params={"user_login": username},
            headers=headers,
            timeout=10,
        ) as resp:
            if resp.status == 401:
                # token expiré, on le régénère au prochain passage
                self._twitch_token = None
                return
            data = await resp.json()

        is_live = bool(data.get("data"))
        was_live = entry.get("was_live", False)

        if is_live and not was_live:
            stream = data["data"][0]
            channel = guild.get_channel(entry["channel_id"])
            if channel:
                await channel.send(
                    f"🟣 **{username}** est en live sur Twitch : *{stream.get('title', '')}*\n"
                    f"https://twitch.tv/{username}"
                )
        entry["was_live"] = is_live

    async def _check_tiktok(self, guild: discord.Guild, entry: dict):
        """TikTok n'a pas d'API publique gratuite : on lit la page publique du profil
        et on en extrait la vidéo la plus récente. Best-effort : peut casser si TikTok
        change la structure de ses pages, mais fonctionne généralement bien."""
        username = entry.get("tiktok_username")
        if not username:
            return

        session = await self.get_session()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        }
        url = f"https://www.tiktok.com/@{username}"
        try:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    return
                html = await resp.text()
        except Exception:
            return

        # La première occurrence d'un ID vidéo dans la page publique correspond
        # généralement à la publication la plus récente du profil.
        video_match = re.search(r'/video/(\d{15,20})', html)
        if not video_match:
            return
        latest_id = video_match.group(1)

        desc_match = re.search(r'"desc":"([^"]{0,150})"', html)
        latest_desc = desc_match.group(1) if desc_match else "Nouvelle vidéo TikTok"

        if entry.get("last_video_id") is None:
            # première vérification : mémorise sans annoncer, pour ne pas spammer l'historique
            entry["last_video_id"] = latest_id
            return

        if latest_id != entry["last_video_id"]:
            entry["last_video_id"] = latest_id
            channel = guild.get_channel(entry["channel_id"])
            if channel:
                await channel.send(
                    f"🎵 Nouvelle vidéo TikTok de **{username}** : {latest_desc}\n"
                    f"https://www.tiktok.com/@{username}/video/{latest_id}"
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(SocialAlerts(bot))
