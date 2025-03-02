import asyncio
import collections
from typing import Dict, List, Optional

import discord
from discord import app_commands

from alexBot.classes import ButtonRole, ButtonType
from alexBot.tools import Cog


def make_callback(btnRole: ButtonRole, otherRoles: List[ButtonRole]):
    """
    if otherRoles is set, it will remove all other roles in the list from the user
    """

    async def callback(interaction: discord.Interaction):
        assert isinstance(interaction.user, discord.Member)
        assert isinstance(interaction.guild, discord.Guild)

        roles = [interaction.guild.get_role(role.role) for role in otherRoles if role.role != btnRole.role]
        if any([role.id in [r.id for r in interaction.user.roles] for role in roles]):
            asyncio.get_event_loop().create_task(interaction.user.remove_roles(*roles))
        role = interaction.guild.get_role(btnRole.role)
        if not role:
            await interaction.response.send_message(
                "that role doesn't exist anymore, please contact an admin", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        if interaction.user.get_role(btnRole.role):
            await interaction.user.remove_roles(role)
            await interaction.followup.send(
                f"removed the {btnRole.label if btnRole.label else str(role.color)} role for you!", ephemeral=True
            )
        else:
            await interaction.user.add_roles(role)
            await interaction.followup.send(
                f"added the {btnRole.label if btnRole.label else str(role.color)} role for you!", ephemeral=True
            )

    return callback


ALLOWMANYROLES = collections.defaultdict(lambda: True)
ALLOWMANYROLES[ButtonType.LOCATION] = False
ALLOWMANYROLES[ButtonType.COLOR] = False


class autoRoles(Cog):
    roles: Dict[ButtonType, List[ButtonRole]] = {}
    views: Dict[ButtonType, discord.ui.View] = {}
    flat_roles: List[ButtonRole] = []

    async def reload_roles(self, btnType: ButtonType):
        await self.cog_load()
        await (await self.bot.get_channel(791528974442299415).fetch_message(self.roles[btnType][0].message)).edit(
            view=self.views[btnType]
        )

    async def cog_load(self):
        self.views = {btnType: discord.ui.View(timeout=None) for btnType in ButtonType}
        self.flat_roles = await self.bot.db.get_roles_data()
        for type in ButtonType:
            self.roles[type] = [r for r in self.flat_roles if r.type == type]

        for type in ButtonType:
            for role in self.roles[type]:
                btn = discord.ui.Button(
                    label=role.label,
                    emoji=role.emoji,
                    custom_id=f"nerdiowo-roleRequest-{role.role}",
                )

                btn.callback = make_callback(role, [] if ALLOWMANYROLES[type] else self.roles[type])

                self.views[type].add_item(btn)
            self.bot.add_view(self.views[type], message_id=self.roles[type][0].message)

    nerdiowo_roles = app_commands.Group(
        name="nerdiowo-roles",
        description="nerdiowo roles menu",
        guild_ids=[791528974442299412],
        default_permissions=discord.Permissions(manage_roles=True),
    )

    @nerdiowo_roles.command(name="reload", description="reload the roles menu")
    async def reload(self, interaction: discord.Interaction, btntype: ButtonType):
        await self.reload_roles(btntype)
        await interaction.response.send_message("done", ephemeral=True)

    @nerdiowo_roles.command(name="add-new-role", description="add a new role to the role request menu")
    async def role_create(
        self,
        interaction: discord.Interaction,
        btntype: ButtonType,
        name: str,
        emoji: Optional[str],
    ):
        try:
            v = discord.ui.View()
            v.add_item(discord.ui.Button(label=name, emoji=emoji))
            await interaction.response.send_message(
                f"adding role {name} to {btntype.name}",
                view=v,
                allowed_mentions=discord.AllowedMentions(roles=False),
            )
        except discord.HTTPException:
            await interaction.response.send_message("invalid emoji", ephemeral=True)
            return
        if name.isnumeric():
            # get that role and use that instead
            role = interaction.guild.get_role(int(name))
            if not role:
                await interaction.followup.send("role not found", ephemeral=True)
                return
            name = role.name  # otherwise the name would be the id
        else:
            role = await interaction.guild.create_role(
                name=name,
                permissions=discord.Permissions.none(),
                mentionable=True,
                reason=f"nerdiowo role requested by {interaction.user}",
            )
        mid = self.roles[btntype][0].message
        br = ButtonRole(role=role.id, message=mid, type=btntype, label=name, emoji=str(emoji) if emoji else None)
        self.roles[btntype].append(br)
        self.flat_roles.append(br)
        await self.bot.db.save_roles_data(self.flat_roles)
        await self.cog_load()
        await (await self.bot.get_channel(791528974442299415).fetch_message(mid)).edit(view=self.views[btntype])
        await interaction.followup.send("added role")
        msg = await self.bot.get_channel(791528974442299415).send(f'added role {role.mention}')
        await asyncio.sleep(60 * 60 * 24)  # wait 24 hours  before deleting the message
        await msg.delete()  # ghost ping the channel

    @nerdiowo_roles.command(name="remove-role", description="remove a role from the role request menu")
    async def role_remove(self, interaction: discord.Interaction, btntype: ButtonType, role: str):
        role: ButtonRole = discord.utils.get(self.roles[btntype], role=int(role))
        if not role:
            await interaction.response.send_message("role not found, or wrong btnType", ephemeral=True)
            return
        self.roles[btntype] = [r for r in self.roles[btntype] if r.role != role.role]
        self.flat_roles = [r for r in self.flat_roles if r.role != role.role]

        await self.bot.db.save_roles_data(self.flat_roles)
        await self.cog_load()
        await (await self.bot.get_channel(791528974442299415).fetch_message(self.roles[btntype][0].message)).edit(
            view=self.views[btntype]
        )
        await interaction.response.send_message("removed role")

    @role_remove.autocomplete('role')
    async def rr_ac_role(self, interaction: discord.Interaction, guess: str) -> List[app_commands.Choice]:
        roles = self.flat_roles
        if interaction.namespace.btnType:
            roles = self.roles[interaction.namespace.btnType]
        return [
            app_commands.Choice(name=role.label, value=str(role.role))
            for role in roles
            if guess.lower() in role.label.lower()
        ]


async def setup(bot):
    await bot.add_cog(autoRoles(bot))
