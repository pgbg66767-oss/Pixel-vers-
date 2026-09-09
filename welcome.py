import json
import os
import discord
from discord.ext import commands

DATA_FILE = "welcome_config.json"


def load_config():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_guild_config(self, guild_id: int):
        config = load_config()
        return config.get(str(guild_id))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = self.get_guild_config(member.guild.id)
        if not config or not config.get("welcome_enabled"):
            return
        channel_id = config.get("channel_id")
        if not channel_id:
            return
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return
        message = config.get("welcome_message", "Bienvenue {membre} sur le serveur !")
        await channel.send(message.replace("{membre}", member.mention))

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        config = self.get_guild_config(member.guild.id)
        if not config or not config.get("goodbye_enabled"):
            return
        channel_id = config.get("channel_id")
        if not channel_id:
            return
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return
        message = config.get("goodbye_message", "{membre} a quitté le serveur.")
        await channel.send(message.replace("{membre}", str(member)))


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
