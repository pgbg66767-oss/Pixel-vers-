import discord
from discord import app_commands
from discord.ext import commands


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Affiche les statistiques du serveur")
    async def stats(self, interaction: discord.Interaction):
        guild = interaction.guild
        total = guild.member_count
        online = sum(1 for m in guild.members if m.status != discord.Status.offline)
        bots = sum(1 for m in guild.members if m.bot)
        humans = total - bots

        embed = discord.Embed(title=f"📊 Statistiques de {guild.name}", color=discord.Color.blurple())
        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        embed.add_field(name="Membres totaux", value=str(total), inline=True)
        embed.add_field(name="Humains", value=str(humans), inline=True)
        embed.add_field(name="Bots", value=str(bots), inline=True)
        embed.add_field(name="En ligne", value=str(online), inline=True)
        embed.add_field(name="Salons textuels", value=str(len(guild.text_channels)), inline=True)
        embed.add_field(name="Salons vocaux", value=str(len(guild.voice_channels)), inline=True)
        embed.add_field(name="Rôles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Créé le", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Affiche les infos d'un membre")
    async def userinfo(self, interaction: discord.Interaction, membre: discord.Member = None):
        membre = membre or interaction.user
        embed = discord.Embed(title=f"👤 {membre}", color=membre.color)
        embed.set_thumbnail(url=membre.display_avatar.url)
        embed.add_field(name="A rejoint le", value=membre.joined_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="Compte créé le", value=membre.created_at.strftime("%d/%m/%Y"), inline=True)
        roles = ", ".join(r.mention for r in membre.roles[1:]) or "Aucun"
        embed.add_field(name="Rôles", value=roles, inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
