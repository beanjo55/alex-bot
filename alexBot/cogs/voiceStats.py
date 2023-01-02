import datetime
import logging
from typing import Optional, Union

import discord
from discord.ext import commands

from alexBot.classes import GuildData, UserData, VoiceStat
from alexBot.tools import Cog

log = logging.getLogger(__name__)


class VoiceStats(Cog):
    @Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        if before.channel is not None and after.channel is not None:  # check that joined or left a voice call
            return
        channel = before.channel or after.channel
        # ?? can we gather data from this guild?
        gd = await self.bot.db.get_guild_data(channel.guild.id)
        if not gd.config.collectVoiceData:
            return

        # ?? are we getting an event for someone leaving?
        if before.channel:
            LEAVING = True
        else:
            LEAVING = False
        # ?? were they the last person?
        if len([m for m in channel.members if not m.bot]) == 0:
            LAST = True
        else:
            LAST = False
        if not LEAVING and len([m for m in after.channel.members if not m.bot]) == 1:
            FIRST = True
        else:
            FIRST = False
        if LEAVING and LAST:
            # definitly ending of a call
            await self.ending_a_call(channel, gd)

        if not LEAVING and FIRST:
            await self.starting_a_call(channel, gd)

        ud = await self.bot.db.get_user_data(member.id)
        if LEAVING:
            await self.member_leaving_call(member, channel, ud)
        else:
            await self.member_joining_call(member, channel, ud)

        log.debug(f"{LAST=}, {LEAVING=}, {FIRST=}")

    async def starting_a_call(self, channel: discord.VoiceChannel, guildData: GuildData):
        log.debug(f"starting a call: {channel=}")
        if guildData.voiceStat.currently_running:
            log.debug("second call started in guild")
            return
        guildData.voiceStat.last_started = datetime.datetime.now()
        guildData.voiceStat.currently_running = True

        await self.bot.db.save_guild_data(channel.guild.id, guildData)

    async def member_joining_call(self, member: discord.Member, channel: discord.VoiceChannel, userData: UserData):
        log.debug(f"{member=} joined {channel=}")

        userData.voiceStat.last_started = datetime.datetime.now()
        userData.voiceStat.currently_running = True

        await self.bot.db.save_user_data(member.id, userData)

    async def member_leaving_call(self, member: discord.Member, channel: discord.VoiceChannel, userData: UserData):
        log.debug(f"{member=} left {channel=}")
        if not userData.voiceStat.currently_running:
            # odd state, ignore
            return
        current_session_length = datetime.datetime.now() - userData.voiceStat.last_started
        if userData.voiceStat.longest_session < current_session_length:
            userData.voiceStat.longest_session = current_session_length

        userData.voiceStat.average_duration_raw = (
            (userData.voiceStat.total_sessions * userData.voiceStat.average_duration_raw)
            + current_session_length.total_seconds()
        ) / (userData.voiceStat.total_sessions + 1)
        userData.voiceStat.total_sessions += 1
        userData.voiceStat.currently_running = False
        await self.bot.db.save_user_data(member.id, userData)
        return

    async def ending_a_call(self, channel: discord.VoiceChannel, gd: GuildData):
        log.debug(f"ending a call: {channel=}")
        guild = channel.guild
        if self.any_other_voice_chats(guild):
            log.debug("late return: other VC in guild")
            return  # the call continues in another channel
        if not gd.voiceStat.currently_running:
            # odd state, ignore
            return
        current_session_length = datetime.datetime.now() - gd.voiceStat.last_started
        if gd.voiceStat.longest_session < current_session_length:
            gd.voiceStat.longest_session = current_session_length

        gd.voiceStat.average_duration_raw = (
            (gd.voiceStat.total_sessions * gd.voiceStat.average_duration_raw) + current_session_length.total_seconds()
        ) / (gd.voiceStat.total_sessions + 1)
        gd.voiceStat.total_sessions += 1
        gd.voiceStat.currently_running = False
        await self.bot.db.save_guild_data(channel.guild.id, gd)

    @commands.command()
    async def voiceStats(self, ctx: commands.Context, target: Optional[Union[discord.Member, discord.Guild]]):
        """tells you how long your average, longest, and current voice sessions is."""
        targets = [ctx.author, ctx.guild] if target is None else [target]
        embed = discord.Embed()
        for target in targets:
            prefix = ""
            vs: VoiceStat = None
            if isinstance(target, discord.Member):
                prefix = f"{target.display_name}'s "
                vs = (await self.bot.db.get_user_data(target.id)).voiceStat
            elif isinstance(target, discord.Guild):
                prefix = f"{target.name}'s "
                vs = (await self.bot.db.get_guild_data(target.id)).voiceStat
            if vs is None:
                return
            if self.any_other_voice_chats(target) if isinstance(target, discord.Guild) else vs.currently_running:
                embed.add_field(
                    name=f"{prefix}Current Session Length",
                    value=datetime.timedelta(seconds=int((datetime.datetime.now() - vs.last_started).total_seconds())),
                )
            embed.add_field(name=f"{prefix}longest session", value=vs.longest_session)
            embed.add_field(name=f"{prefix}Average Session Length", value=vs.average_duration)
            embed.add_field(name=f"{prefix}Total Sessions", value=vs.total_sessions)
        await ctx.send(embed=embed)

    @staticmethod
    def any_other_voice_chats(guild: discord.Guild) -> bool:
        return any([len([m for m in vc.members if not m.bot]) > 0 for vc in guild.voice_channels])


async def setup(bot):
    await bot.add_cog(VoiceStats(bot))
