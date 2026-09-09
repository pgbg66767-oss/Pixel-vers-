import time
import discord
from discord import app_commands
from discord.ext import commands
from collections import defaultdict

# Anti-spam : nombre de messages max autorisés dans la fenêtre de temps
SPAM_LIMIT = 5
SPAM_WINDOW = 6  # secondes


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_log = defaultdict(list)  # {user_id: [timestamps]}
        self.log_channel_name = "logs-modération"

    # ---------- Anti-spam ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        now = time.time()
        history = self.message_log[message.author.id]
        history.append(now)
        # ne garder que les messages dans la fenêtre de temps
        self.message_log[message.author.id] = [t for t in history if now - t < SPAM_WINDOW]

        if len(self.message_log[message.author.id]) > SPAM_LIMIT:
            try:
                await message.channel.send(
                    f"⚠️ {message.author.mention}, ralentis un peu, tu envoies des messages trop vite.",
                    delete_after=6,
                )
                timeout_duration = discord.utils.utcnow() + discord.timedelta(minutes=5)
                await message.author.timeout(timeout_duration, reason="Anti-spam automatique")
                await self.log(message.guild, f"🔇 {message.author.mention} mute 5 min (anti-spam).")
            except discord.Forbidden:
                pass
            self.message_log[message.author.id] = []

    async def log(self, guild: discord.Guild, text: str):
        channel = discord.utils.get(guild.text_channels, name=self.log_channel_name)
        if channel:
            await channel.send(text)

    # ---------- Commandes slash ----------
    @app_commands.command(name="kick", description="Expulse un membre du serveur")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Non précisée"):
        await membre.kick(reason=raison)
        await interaction.response.send_message(f"👢 {membre.mention} a été expulsé. Raison : {raison}")
        await self.log(interaction.guild, f"👢 {membre.mention} expulsé par {interaction.user.mention} — {raison}")

    @app_commands.command(name="ban", description="Bannit un membre du serveur")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Non précisée"):
        await membre.ban(reason=raison)
        await interaction.response.send_message(f"🔨 {membre.mention} a été banni. Raison : {raison}")
        await self.log(interaction.guild, f"🔨 {membre.mention} banni par {interaction.user.mention} — {raison}")

    @app_commands.command(name="mute", description="Rend un membre muet temporairement (en minutes)")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, membre: discord.Member, minutes: int = 10):
        duration = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
        await membre.timeout(duration, reason=f"Mute manuel par {interaction.user}")
        await interaction.response.send_message(f"🔇 {membre.mention} est mute pour {minutes} minute(s).")
        await self.log(interaction.guild, f"🔇 {membre.mention} mute {minutes}min par {interaction.user.mention}")

    @app_commands.command(name="unmute", description="Retire le mute d'un membre")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, membre: discord.Member):
        await membre.timeout(None)
        await interaction.response.send_message(f"🔊 {membre.mention} n'est plus mute.")

    @app_commands.command(name="clear", description="Supprime un nombre de messages dans le salon")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, nombre: int):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=nombre)
        await interaction.followup.send(f"🧹 {len(deleted)} message(s) supprimé(s).", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
