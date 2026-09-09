import json
import os
import discord
from discord.ext import commands

DATA_FILE = "reaction_roles.json"


def load_config():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def find_entry(self, guild_id: int, message_id: int, emoji: str):
        config = load_config()
        for entry in config.get(str(guild_id), []):
            if entry["message_id"] == message_id and entry["emoji"] == emoji:
                return entry
        return None

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member is None or payload.member.bot:
            return
        entry = self.find_entry(payload.guild_id, payload.message_id, str(payload.emoji))
        if not entry:
            return
        guild = self.bot.get_guild(payload.guild_id)
        role = guild.get_role(entry["role_id"]) if guild else None
        if role:
            await payload.member.add_roles(role, reason="Rôle à la réaction")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        entry = self.find_entry(payload.guild_id, payload.message_id, str(payload.emoji))
        if not entry:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        role = guild.get_role(entry["role_id"])
        if member and role:
            await member.remove_roles(role, reason="Retrait de la réaction")


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))
