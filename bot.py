#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.ext import commands

import config
from alexBot.channel_logging import setup_logging

if TYPE_CHECKING:
    from alexBot.data import Data


cogs = [x.stem for x in Path('alexBot/cogs').glob('*.py') if x.stem not in ["__init__", "sugery"]]
# cogs = ['autoRoles', 'errors']  # used to test single cog at a time
log = logging.getLogger(__name__)

LINKWRAPPERREGEX = re.compile(r'(http[s]?://(?:[a-zA-Z]|[0-9]|[#-_]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)', re.I)


intents = discord.Intents.all()


allowed_mentions = discord.AllowedMentions.none()


class Bot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(command_prefix=config.prefix, intents=intents, allowed_mentions=allowed_mentions, **kwargs)
        self.session = None
        self.logger = logging.getLogger("bot")
        self.config: config = config
        self.location = config.location
        self.db: "Data" = None
        self.owner = None
        logging.getLogger('discord.gateway').setLevel(logging.ERROR)
        self.setup_hook = self.cogSetup
        self.minecraft = True

    async def on_ready(self):
        log.info(f'Logged on as {self.user} ({self.user.id})')
        self.owner = (await self.application_info()).owner
        log.info(f'owner is {self.owner} ({self.owner.id})')
        self.session = aiohttp.ClientSession()

    async def cogSetup(self):
        await self.load_extension("alexBot.data")
        await self.load_extension('jishaku')
        self.db: "Data" = self.get_cog('Data')
        for cog in cogs:
            try:
                await self.load_extension(f"alexBot.cogs.{cog}")
                log.info(f'loaded {cog}')
            except Exception as e:
                log.error(f'Could not load extension {cog} due to {e.__class__.__name__}: {e}')

    @staticmethod
    def clean_mentions(content: str) -> str:
        content = content.replace('`', '\'')
        content = content.replace('@', '@\u200b')
        content = content.replace('&', '&\u200b')
        content = content.replace('<#', '<#\u200b')
        return content

    @staticmethod
    def clean_formatting(content: str) -> str:
        content = content.replace('_', '\\_')
        content = content.replace('*', '\\*')
        content = content.replace('`', '\\`')
        return content

    @staticmethod
    def clean_links(content: str) -> str:
        content = LINKWRAPPERREGEX.sub(r'<\1>', content)
        return content

    def clean_clean(self, content):
        content = self.clean_mentions(content)
        content = self.clean_formatting(content)
        content = self.clean_links(content)
        return content

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        else:
            await self.process_commands(message)

    async def on_command(self, ctx):
        # thanks dogbot ur a good
        content = ctx.message.content
        content = self.clean_mentions(content)

        author = ctx.message.author
        guild = ctx.guild
        checks = [c.__qualname__.split('.')[0] for c in ctx.command.checks]
        location = '[DM]' if isinstance(ctx.channel, discord.DMChannel) else f'[Guild {guild.name} {guild.id}]'

        log.info('%s [cmd] %s(%d) "%s" checks=%s', location, author, author.id, content, ','.join(checks) or '(none)')


loop = asyncio.get_event_loop()

webhooks = {}
session = aiohttp.ClientSession()

for name in config.logging:
    level = getattr(logging, name.upper(), None)
    if level is None:
        continue

    url = config.logging[name]
    webhooks[level] = discord.Webhook.from_url(url, session=session)

with setup_logging(webhooks=webhooks, silenced=['discord', 'websockets', 'aiosqlite']):
    bot = Bot()

    try:
        loop.run_until_complete(bot.start(config.token))
    except KeyboardInterrupt:
        loop.run_until_complete(bot.close())
        loop.run_until_complete(session.close())
