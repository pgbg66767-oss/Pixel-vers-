import json
import os
import discord
from discord import app_commands
from discord.ext import commands

DATA_FILE = "badges.json"


def load_badges():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_badges(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class Badges(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.badges = load_badges()  # { "guild_id": { "user_id": "emoji" } }

    badge_group = app_commands.Group(name="badge", description="Gestion des badges des membres")

    @badge_group.command(name="set", description="Attribue un badge (emoji) à un membre")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_badge(self, interaction: discord.Interaction, membre: discord.Member, emoji: str):
        gid = str(interaction.guild.id)
        self.badges.setdefault(gid, {})
        self.badges[gid][str(membre.id)] = emoji
        save_badges(self.badges)
        await interaction.response.send_message(f"🏅 Badge {emoji} attribué à {membre.mention}.")

    @badge_group.command(name="remove", description="Retire le badge d'un membre")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_badge(self, interaction: discord.Interaction, membre: discord.Member):
        gid = str(interaction.guild.id)
        if gid in self.badges and str(membre.id) in self.badges[gid]:
            del self.badges[gid][str(membre.id)]
            save_badges(self.badges)
            await interaction.response.send_message(f"🗑️ Badge retiré à {membre.mention}.")
        else:
            await interaction.response.send_message(f"{membre.mention} n'a pas de badge.", ephemeral=True)

    @badge_group.command(name="list", description="Liste tous les membres ayant un badge")
    async def list_badges(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        entries = self.badges.get(gid, {})
        if not entries:
            await interaction.response.send_message("Aucun badge attribué sur ce serveur.", ephemeral=True)
            return
        lines = []
        for uid, emoji in entries.items():
            member = interaction.guild.get_member(int(uid))
            if member:
                lines.append(f"{emoji} — {member.mention}")
        await interaction.response.send_message("\n".join(lines) or "Aucun badge actif.")

    # ---------- Réaction automatique ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        gid = str(message.guild.id)
        uid = str(message.author.id)
        emoji = self.badges.get(gid, {}).get(uid)
        if emoji:
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                pass  # emoji invalide ou permissions manquantes


async def setup(bot: commands.Bot):
    await bot.add_cog(Badges(bot))
