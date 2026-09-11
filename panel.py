import os
import discord
from discord import app_commands
from discord.ext import commands


class Panel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="panel", description="Affiche le lien du tableau de bord web du serveur")
    async def panel(self, interaction: discord.Interaction):
        panel_url = os.getenv("PANEL_URL")

        if not panel_url:
            # Repli automatique : on déduit l'URL du site à partir de DISCORD_REDIRECT_URI
            # (ex: https://xxx.up.railway.app/callback -> https://xxx.up.railway.app)
            redirect_uri = os.getenv("DISCORD_REDIRECT_URI", "")
            panel_url = redirect_uri.replace("/callback", "") if redirect_uri else None

        embed = discord.Embed(
            title="🖥️ Tableau de bord",
            description=(
                f"[Clique ici pour accéder au panel]({panel_url})" if panel_url
                else "⚠️ Aucune URL de panel n'est configurée (variable `PANEL_URL` manquante)."
            ),
            color=discord.Color.blue(),
        )
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Panel(bot))
