import asyncio
from typing import Dict

import discord
from discord import app_commands

from alexBot.classes import RingRate
from alexBot.tools import Cog


def mk_callback(task: asyncio.Task):
    async def callback(interaction: discord.Interaction):
        task.cancel()
        await interaction.response.send_message("canceled ringing", ephemeral=True)

    return callback


class Ringing(Cog):
    class CancelableTaskView(discord.ui.View):
        def __init__(self, task: asyncio.Task):
            super().__init__(timeout=240)
            btn = discord.ui.Button(label="cancel", style=discord.ButtonStyle.danger)
            btn.callback = mk_callback(task)
            self.add_item(btn)

    @app_commands.command()
    @app_commands.guild_only()
    async def ring(self, interaction: discord.Interaction, target: discord.Member):
        """Alerts another member of the server that you want someone to talk to. requires that you're in a voice channel."""
        if not interaction.user.voice:
            await interaction.response.send_message("cannot ring: you are not in a voice channel", ephemeral=True)
            return

        if target.voice:
            await interaction.response.send_message("cannot ring: they are already in voice", ephemeral=True)
            return

        if not (await self.bot.db.get_user_data(target.id)).config.ringable:
            await interaction.response.send_message("cannot ring: they do not want to be rung", ephemeral=True)
            return

        ringRate = self.bot.config.ringRates[target.status]
        task = asyncio.create_task(self.doRing(interaction.user, target, interaction.channel, ringRate))
        await interaction.response.send_message("ringing...", view=self.CancelableTaskView(task))
        try:
            await task
        except asyncio.CancelledError:
            pass
        await (await interaction.original_response()).edit(view=None)

    async def doRing(
        self,
        initiator: discord.Member,
        target: discord.Member,
        channel: discord.TextChannel,
        ringRate: RingRate = RingRate(),
    ):
        times = 0
        allowed_mentions = discord.AllowedMentions(users=[target])

        while times <= ringRate.times:
            if channel.guild.get_member(target.id).voice:
                return  #  they joined voice
            await channel.send(
                f"HELLO, {target.mention}! {initiator.name.upper()} WANTS YOU TO JOIN {initiator.voice.channel.mention}!",
                allowed_mentions=allowed_mentions,
            )
            await asyncio.sleep(ringRate.rate)

            times += 1


async def setup(bot):
    await bot.add_cog(Ringing(bot))
