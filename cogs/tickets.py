import io
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

TICKET_CATEGORY_NAME = "Tickets"


class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ouvrir un ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        author = interaction.user

        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        existing = discord.utils.get(guild.text_channels, name=f"ticket-{author.name}".lower())
        if existing:
            await interaction.response.send_message(f"Tu as déjà un ticket ouvert : {existing.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            author: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        channel = await guild.create_text_channel(
            f"ticket-{author.name}", category=category, overwrites=overwrites
        )
        await channel.send(
            f"👋 Bienvenue {author.mention} ! Le staff va bientôt te répondre.",
            view=CloseTicketView(),
        )
        await interaction.response.send_message(f"🎫 Ton ticket a été créé : {channel.mention}", ephemeral=True)


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel

        # Génère un transcript basique avant de supprimer le salon
        messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]
        transcript_lines = [f"{m.author}: {m.content}" for m in messages if m.content]
        transcript = "\n".join(transcript_lines) or "(aucun message)"

        log_channel = discord.utils.get(interaction.guild.text_channels, name="logs-tickets")
        if log_channel:
            file_content = transcript.encode("utf-8")
            await log_channel.send(
                f"📋 Transcript du ticket **{channel.name}** (fermé par {interaction.user.mention})",
                file=discord.File(fp=io.BytesIO(file_content), filename=f"{channel.name}.txt"),
            )

        await interaction.response.send_message("🔒 Ticket fermé, suppression dans 5 secondes...")
        await asyncio.sleep(5)
        await channel.delete()


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Réenregistre les vues persistantes au redémarrage du bot
        bot.add_view(TicketButton())
        bot.add_view(CloseTicketView())

    @app_commands.command(name="ticket-setup", description="Poste le message avec le bouton d'ouverture de ticket")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_setup(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 Support",
            description="Clique sur le bouton ci-dessous pour ouvrir un ticket privé avec le staff.",
            color=discord.Color.blurple(),
        )
        await interaction.channel.send(embed=embed, view=TicketButton())
        await interaction.response.send_message("✅ Message de ticket envoyé.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
