import logging
from attr import dataclass
from alexBot.tools import Cog
from discord.ext import commands
import datetime
import discord

log = logging.getLogger(__name__)


@dataclass
class VoiceData:
    longest_session_int: int
    last_started_int: int
    currently_running: bool

    @property
    def longest_session(self) -> datetime.timedelta:
        """
        the length of the longest Session, as returned as a `Datetime.timespan`
        """
        return datetime.timedelta(seconds=self.longest_session_int)

    @longest_session.setter
    def longest_session(self, value: datetime.timedelta):
        self.longest_session_int = value.total_seconds()

    @property
    def last_started(self) -> datetime.datetime:
        """
        the start time of the current session. only valid if self.currentlyRunning == true
        """
        return datetime.datetime.fromtimestamp(self.last_started_int)

    @last_started.setter
    def last_started(self, value: datetime.datetime):
        self.last_started_int = int(value.timestamp())


class VoiceStats(Cog):
    @Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is not None and after.channel is not None:  # check that joined or left a voice call
            log.debug("early return")
            return
        channel = before.channel or after.channel
        # ?? are we getting an event for someone leaving?
        if before.channel:
            LEAVING = True
        else:
            LEAVING = False
        # ?? were they the last person?
        if len(channel.members) == 0:
            LAST = True
        else:
            LAST = False
        if not LEAVING and len(after.channel.members) == 1:
            FIRST = True
        else:
            FIRST = False
        if LEAVING and LAST:
            # definitly ending of a call
            await self.ending_a_call(channel)

        if not LEAVING and FIRST:
            await self.starting_a_call(channel)  # dont forget to check the DB for ongoing call...

        log.debug(f"{LAST=}, {LEAVING=}, {FIRST=}")

    async def starting_a_call(self, channel: discord.VoiceChannel):
        log.debug(f"starting a call: {channel=}")
        vd = await self.get_server_voice_data(channel.guild)
        if vd.currently_running:
            log.debug("second call started in guild")
            return
        vd.last_started = datetime.datetime.now()
        vd.currently_running = True
        await self.save_server_voice_data(channel.guild, vd)

    async def ending_a_call(self, channel: discord.VoiceChannel):
        log.debug(f"ending a call: {channel=}")
        guild = channel.guild
        if any([len(vc.members) > 1 for vc in guild.voice_channels]):
            log.debug("late return: other VC in guild")
            return  # the call continues in another channel
        vd = await self.get_server_voice_data(channel.guild)
        if not vd.currently_running:
            # odd state, ignore
            return
        current_session_length = datetime.datetime.now() - vd.last_started
        if vd.longest_session > current_session_length:
            return  # previous longes session is longer than this session
        vd.longest_session = current_session_length
        vd.currently_running = False
        await self.save_server_voice_data(channel.guild, vd)

    async def get_server_voice_data(self, guild: discord.Guild) -> VoiceData:
        """
        loads a VD from storage
        """
        cur = await self.bot.db.execute("""SELECT longestSession, lastStarted, currentlyRunning FROM voiceData WHERE id=?""", (guild.id,))
        data = await cur.fetchone()
        if not data:
            await self.bot.db.execute("""INSERT INTO voiceData (id, longestSession, lastStarted, currentlyRunning) VALUES (?,?,?,?)""", (guild.id, 0, 0, False))
            await self.bot.db.commit()
            vd = VoiceData(0, 0, False)
        else:
            vd = VoiceData(data[0], data[1], data[2])
        log.debug(f"fetched {vd=} for {guild=}")
        return vd

    async def save_server_voice_data(self, guild: discord.Guild, voiceData: VoiceData) -> None:
        """
        saves the VD to storage
        """
        log.debug(f"saving for {guild=}, {voiceData=}")
        await self.bot.db.execute("""UPDATE voiceData SET longestSession=?, lastStarted=?, currentlyRunning=? WHERE id=?""",
                                  (voiceData.longest_session_int, voiceData.last_started_int, voiceData.currently_running, guild.id))
        await self.bot.db.commit()


def setup(bot):
    bot.add_cog(VoiceStats(bot))
