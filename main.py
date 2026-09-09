import os
import asyncio
import discord
from discord.ext import commands
from webapp.api_server import start_webapp

# --- Configuration de base ---
intents = discord.Intents.default()
intents.message_content = True   # nécessaire pour la modération de texte
intents.members = True           # nécessaire pour les logs d'arrivée/départ et les badges

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Liste des modules (cogs) à charger au démarrage
INITIAL_EXTENSIONS = [
    "cogs.setup",
    "cogs.moderation",
    "cogs.tickets",
    "cogs.badges",
    "cogs.music",
    "cogs.stats",
    "cogs.social_alerts",
    "cogs.welcome",
    "cogs.reaction_roles",
]


@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 {len(synced)} commande(s) slash synchronisée(s)")
    except Exception as e:
        print(f"⚠️ Erreur de synchronisation des commandes : {e}")


async def main():
    async with bot:
        for ext in INITIAL_EXTENSIONS:
            try:
                await bot.load_extension(ext)
                print(f"📦 Module chargé : {ext}")
            except Exception as e:
                print(f"❌ Impossible de charger {ext} : {e}")

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise RuntimeError(
                "❌ DISCORD_TOKEN introuvable. Ajoute-le dans les Secrets de Replit "
                "(cadenas dans la barre latérale gauche)."
            )
        await bot.start(token)


if __name__ == "__main__":
    start_webapp(bot)  # lance le site (dashboard + API) sur le même Repl que le bot
    asyncio.run(main())
