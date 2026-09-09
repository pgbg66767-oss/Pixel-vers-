import json
import os
import discord
from discord import app_commands
from discord.ext import commands

VERIF_CONFIG_FILE = "verification_config.json"
VERIF_EMOJI = "✅"

# --- Définition de la structure créée par /serveur-setup ---

ROLES = [
    {"name": "Admin", "color": discord.Color.red(), "permissions": discord.Permissions(administrator=True), "hoist": True},
    {"name": "Modérateur", "color": discord.Color.orange(), "permissions": discord.Permissions(
        kick_members=True, ban_members=True, moderate_members=True, manage_messages=True
    ), "hoist": True},
    {"name": "Vérifié", "color": discord.Color.green(), "permissions": discord.Permissions(), "hoist": False},
    {"name": "Membre", "color": discord.Color.blue(), "permissions": discord.Permissions(), "hoist": False},
    {"name": "Muted", "color": discord.Color.dark_grey(), "permissions": discord.Permissions(), "hoist": False},
]

# Salons visibles par tout le monde, même avant vérification
PUBLIC_CHANNELS = {"règlement", "vérification", "annonces"}

STRUCTURE = [
    {
        "category": "📌 Informations",
        "channels": [
            {"name": "règlement", "type": "text"},
            {"name": "vérification", "type": "text"},
            {"name": "annonces", "type": "text"},
            {"name": "bienvenue", "type": "text"},
        ],
    },
    {
        "category": "💬 Général",
        "channels": [
            {"name": "général", "type": "text"},
            {"name": "discussion", "type": "text"},
            {"name": "memes", "type": "text"},
        ],
    },
    {
        "category": "🎥 Créateurs",
        "channels": [
            {"name": "vos-vidéos-youtube", "type": "text"},
            {"name": "vos-tiktoks", "type": "text"},
            {"name": "vos-lives-twitch", "type": "text"},
            {"name": "collab-et-entraide", "type": "text"},
        ],
    },
    {
        "category": "🎫 Support",
        "channels": [],  # rempli dynamiquement par le module tickets
    },
    {
        "category": "🔊 Vocaux",
        "channels": [
            {"name": "Général", "type": "voice"},
            {"name": "Musique", "type": "voice"},
        ],
    },
    {
        "category": "🛠️ Staff",
        "channels": [
            {"name": "staff-chat", "type": "text", "staff_only": True},
            {"name": "logs-modération", "type": "text", "staff_only": True},
            {"name": "logs-tickets", "type": "text", "staff_only": True},
        ],
    },
]

REGLEMENT_TEXT = (
    "Bienvenue sur le serveur ! Ce règlement s'applique à tous les membres, y compris dans les salons "
    "dédiés aux créateurs (YouTube, TikTok, Twitch). Merci de le lire en entier avant de réagir plus bas "
    "pour accéder au reste du serveur.\n\n"

    "**🤝 Respect général**\n"
    "**1.** Respecte tous les membres : aucune insulte, harcèlement, discrimination ou incitation à la haine.\n"
    "**2.** Les débats sont autorisés, les attaques personnelles ne le sont pas.\n"
    "**3.** Écoute et respecte les décisions du staff (rôles Admin / Modérateur).\n\n"

    "**🚫 Contenu interdit**\n"
    "**4.** Pas de spam, de publicité non sollicitée en message privé, ni de liens douteux/raccourcis suspects.\n"
    "**5.** Contenu NSFW, choquant ou violent interdit, y compris en avatar/bannière.\n"
    "**6.** Pas de contenu illégal (piratage, cheats, doxxing, etc.).\n\n"

    "**🎥 Règles spécifiques créateurs (YouTube / TikTok / Twitch)**\n"
    "**7.** Poste tes vidéos YouTube uniquement dans #vos-vidéos-youtube, tes TikToks dans #vos-tiktoks, "
    "et annonce tes lives Twitch dans #vos-lives-twitch — pas dans les salons de discussion générale.\n"
    "**8.** Une seule auto-promo par personne et par jour et par salon dédié, pour laisser de la place à tout "
    "le monde.\n"
    "**9.** Le soutien entre créateurs est encouragé (#collab-et-entraide), mais l'échange forcé de vues/"
    "abonnés (\"sub4sub\", \"like4like\") n'est pas autorisé.\n"
    "**10.** Crédite toujours les créateurs originaux si tu repartages un contenu qui n'est pas le tien.\n\n"

    "**⚖️ Sanctions**\n"
    "Le non-respect de ce règlement peut entraîner, selon la gravité et la répétition : un avertissement, "
    "un mute temporaire, un kick, ou un ban définitif. Le staff se réserve le droit de juger au cas par cas.\n\n"

    f"**Pour accéder au reste du serveur, réagis avec {VERIF_EMOJI} juste en dessous.**"
)


def load_verif_config():
    if not os.path.exists(VERIF_CONFIG_FILE):
        return {}
    with open(VERIF_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_verif_config(data):
    with open(VERIF_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class ServerSetup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="serveur-setup",
        description="Crée automatiquement les rôles, salons, le règlement et la vérification par réaction",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def serveur_setup(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        guild = interaction.guild
        report = []

        # ---------- 1. Rôles ----------
        created_roles = {}
        for r in ROLES:
            existing = discord.utils.get(guild.roles, name=r["name"])
            if existing:
                created_roles[r["name"]] = existing
                continue
            role = await guild.create_role(
                name=r["name"],
                color=r["color"],
                permissions=r["permissions"],
                hoist=r["hoist"],
                reason="Créé par /serveur-setup",
            )
            created_roles[r["name"]] = role
            report.append(f"✅ Rôle **{r['name']}** créé")

        muted_role = created_roles["Muted"]
        verified_role = created_roles["Vérifié"]
        staff_roles = [created_roles["Admin"], created_roles["Modérateur"]]

        # ---------- 2. Catégories et salons ----------
        verification_channel = None
        for group in STRUCTURE:
            category = discord.utils.get(guild.categories, name=group["category"])
            if not category:
                category = await guild.create_category(group["category"], reason="Créé par /serveur-setup")
                report.append(f"✅ Catégorie **{group['category']}** créée")

            for chan in group["channels"]:
                slug = chan["name"].lower().replace(" ", "-")
                existing_chan = discord.utils.get(category.channels, name=slug)
                if existing_chan:
                    if chan["name"] == "vérification":
                        verification_channel = existing_chan
                    continue

                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(send_messages=None, speak=None)
                }
                overwrites[muted_role] = discord.PermissionOverwrite(send_messages=False, speak=False)

                if chan.get("staff_only"):
                    overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                    for sr in staff_roles:
                        overwrites[sr] = discord.PermissionOverwrite(view_channel=True)
                elif chan["name"] not in PUBLIC_CHANNELS:
                    # Salon caché tant qu'on n'a pas le rôle Vérifié
                    overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                    overwrites[verified_role] = discord.PermissionOverwrite(view_channel=True)

                if chan["type"] == "text":
                    new_channel = await guild.create_text_channel(
                        chan["name"], category=category, overwrites=overwrites
                    )
                else:
                    new_channel = await guild.create_voice_channel(
                        chan["name"], category=category, overwrites=overwrites
                    )
                report.append(f"✅ Salon **{new_channel.name}** créé")

                if chan["name"] == "vérification":
                    verification_channel = new_channel

                if chan["name"] == "règlement":
                    embed = discord.Embed(
                        title="📜 Règlement du serveur",
                        description=REGLEMENT_TEXT,
                        color=discord.Color.blue(),
                    )
                    await new_channel.send(embed=embed)

        # ---------- 3. Message de vérification par réaction ----------
        if verification_channel:
            verif_config = load_verif_config()
            existing_entry = verif_config.get(str(guild.id))
            already_posted = False
            if existing_entry:
                try:
                    await verification_channel.fetch_message(existing_entry["message_id"])
                    already_posted = True
                except discord.NotFound:
                    already_posted = False

            if not already_posted:
                verif_embed = discord.Embed(
                    title="✅ Vérification",
                    description=(
                        f"Réagis avec {VERIF_EMOJI} sur ce message pour débloquer l'accès à tout le serveur, "
                        "après avoir lu le règlement dans #règlement."
                    ),
                    color=discord.Color.green(),
                )
                verif_message = await verification_channel.send(embed=verif_embed)
                await verif_message.add_reaction(VERIF_EMOJI)

                verif_config[str(guild.id)] = {
                    "channel_id": verification_channel.id,
                    "message_id": verif_message.id,
                    "role_id": verified_role.id,
                }
                save_verif_config(verif_config)
                report.append("✅ Message de vérification par réaction posté")

        # ---------- 4. Rapport final ----------
        summary = "\n".join(report) if report else "Rien à créer, tout existait déjà."
        if len(summary) > 3900:
            summary = summary[:3900] + "\n… (tronqué)"

        result_embed = discord.Embed(
            title="🛠️ Setup terminé",
            description=summary,
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=result_embed)

    @serveur_setup.error
    async def serveur_setup_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Il faut être administrateur pour utiliser cette commande.", ephemeral=True
            )
        else:
            raise error

    # ---------- Attribution du rôle Vérifié à la réaction ----------
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member is None or payload.member.bot:
            return
        if str(payload.emoji) != VERIF_EMOJI:
            return

        verif_config = load_verif_config()
        entry = verif_config.get(str(payload.guild_id))
        if not entry or payload.message_id != entry["message_id"]:
            return

        guild = self.bot.get_guild(payload.guild_id)
        role = guild.get_role(entry["role_id"]) if guild else None
        if role:
            await payload.member.add_roles(role, reason="Vérification par réaction")


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSetup(bot))
