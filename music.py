import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

YDL_OPTIONS = {"format": "bestaudio", "noplaylist": True, "quiet": True}
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queues = {}  # {guild_id: [ (title, url) ]}

    def get_queue(self, guild_id):
        return self.queues.setdefault(guild_id, [])

    @app_commands.command(name="play", description="Joue une musique depuis YouTube (nom ou lien)")
    async def play(self, interaction: discord.Interaction, recherche: str):
        if not interaction.user.voice:
            await interaction.response.send_message("❌ Tu dois être dans un salon vocal.", ephemeral=True)
            return

        await interaction.response.defer()
        voice_channel = interaction.user.voice.channel
        vc = interaction.guild.voice_client or await voice_channel.connect()

        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(f"ytsearch:{recherche}", download=False)["entries"][0]
            url = info["url"]
            title = info["title"]

        queue = self.get_queue(interaction.guild.id)
        queue.append((title, url))

        if not vc.is_playing():
            await self._play_next(interaction.guild, vc)
            await interaction.followup.send(f"▶️ Lecture : **{title}**")
        else:
            await interaction.followup.send(f"➕ Ajouté à la file d'attente : **{title}**")

    async def _play_next(self, guild: discord.Guild, vc: discord.VoiceClient):
        queue = self.get_queue(guild.id)
        if not queue:
            return
        title, url = queue.pop(0)
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)

        def after_play(error):
            fut = self._play_next(guild, vc)
            asyncio.run_coroutine_threadsafe(fut, self.bot.loop)

        vc.play(source, after=after_play)

    @app_commands.command(name="skip", description="Passe à la musique suivante")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Musique passée.")
        else:
            await interaction.response.send_message("Rien ne joue actuellement.", ephemeral=True)

    @app_commands.command(name="stop", description="Arrête la musique et vide la file d'attente")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        self.get_queue(interaction.guild.id).clear()
        if vc:
            await vc.disconnect()
        await interaction.response.send_message("⏹️ Musique arrêtée.")

    @app_commands.command(name="queue", description="Affiche la file d'attente")
    async def queue_cmd(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if not queue:
            await interaction.response.send_message("La file d'attente est vide.", ephemeral=True)
            return
        text = "\n".join(f"{i+1}. {t}" for i, (t, _) in enumerate(queue))
        await interaction.response.send_message(f"🎶 File d'attente :\n{text}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
