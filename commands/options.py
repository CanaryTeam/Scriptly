import discord
from discord import ui
from discord.ext import commands
from typing import List, Optional

class AddChannelModal(ui.Modal, title="Add Channel to Restriction"):
    channel_id_input = ui.TextInput(
        label="Channel ID",
        placeholder="Enter the numerical ID of the channel",
        required=True,
        min_length=17,
        max_length=20
    )

    def __init__(self, view: 'OptionsView'):
        super().__init__(timeout=300)
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id_input.value.strip())
            channel = interaction.guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message("Invalid Text Channel ID for this server.", ephemeral=True)
                return

            if channel_id in self.view.restricted_channels:
                await interaction.response.send_message(f"{channel.mention} is already in the list.", ephemeral=True)
                return

            self.view.restricted_channels.append(channel_id)
            await self.view.update_message(interaction, status_message=f"Added {channel.mention} to the list.")

        except ValueError:
            await interaction.response.send_message("Invalid input. Please enter a numerical Channel ID.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

class OptionsView(ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int, initial_channels: Optional[List[int]]):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.is_restricted = initial_channels is not None
        self.restricted_channels = initial_channels or []
        self.original_state = (self.is_restricted, list(self.restricted_channels))
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()

        toggle_label = "Disable Channel Restriction" if self.is_restricted else "Enable Channel Restriction"
        toggle_style = discord.ButtonStyle.danger if self.is_restricted else discord.ButtonStyle.success
        self.toggle_button = ui.Button(label=toggle_label, style=toggle_style, custom_id="toggle_restriction")
        self.toggle_button.callback = self.toggle_restriction
        self.add_item(self.toggle_button)

        self.add_channel_button = ui.Button(label="Add Allowed Channel", style=discord.ButtonStyle.primary, disabled=not self.is_restricted, custom_id="add_channel")
        self.add_channel_button.callback = self.add_channel
        self.add_item(self.add_channel_button)

        self.remove_channel_button = ui.Button(label="Remove Allowed Channel", style=discord.ButtonStyle.secondary, disabled=not self.is_restricted or not self.restricted_channels, custom_id="remove_channel")
        if self.restricted_channels:
             self.remove_channel_button.callback = self.remove_channel_select
        self.add_item(self.remove_channel_button)


        self.save_button = ui.Button(label="Save Configuration", style=discord.ButtonStyle.success, custom_id="save_config", disabled=not self._has_changes())
        self.save_button.callback = self.save_configuration
        self.add_item(self.save_button)

        self.cancel_button = ui.Button(label="Cancel", style=discord.ButtonStyle.grey, custom_id="cancel_changes")
        self.cancel_button.callback = self.cancel_changes
        self.add_item(self.cancel_button)


    def _build_embed(self, status_message: Optional[str] = None) -> discord.Embed:
        title = "Scriptly Server Options"
        config_status = "Unsaved changes" if self._has_changes() else "Configuration saved" if hasattr(self, 'saved_once') else "Current configuration"

        desc = f"⚙️ **Status:** {config_status}\n"
        if status_message:
             desc += f"ℹ️ __{status_message}__\n\n"
        else:
             desc += "\n"


        restriction_status = "✅ Enabled" if self.is_restricted else "❌ Disabled"
        desc += f"Channel Restriction: **{restriction_status}**\n"

        if self.is_restricted:
            if self.restricted_channels:
                mentions = []
                guild = self.bot.get_guild(self.guild_id)
                if guild:
                    for cid in self.restricted_channels:
                        channel = guild.get_channel(cid)
                        mentions.append(channel.mention if channel else f"`{cid}` (Unknown)")
                else:
                     mentions = [f"`{cid}`" for cid in self.restricted_channels]

                desc += "└ Allowed Channels:\n" + "\n".join([f"   • {m}" for m in mentions])
            else:
                desc += "└ Allowed Channels: **None** (Bot usable nowhere if restriction is enabled)"
        else:
            desc += "└ Bot usable in **all channels**."

        embed = discord.Embed(title=title, description=desc, color=discord.Color.blue())
        embed.set_image(url="https://cdn.discordapp.com/attachments/1357547210916626594/1362639312675405914/9fpOS21.png?ex=68032040&is=6801cec0&hm=73cc7078d8659bbeab872afc45c3bdd20560cb3ac611c81a92a7631a9ebb72d6&")
        embed.set_footer(text="Changes are temporary until saved.")
        return embed

    def _has_changes(self) -> bool:
         current_state = (self.is_restricted, sorted(self.restricted_channels))
         original_state = (self.original_state[0], sorted(self.original_state[1]))
         return current_state != original_state

    async def update_message(self, interaction: discord.Interaction, status_message: Optional[str] = None):
        self._update_buttons()
        embed = self._build_embed(status_message)
        if interaction.response.is_done():
             await interaction.edit_original_response(embed=embed, view=self)
        else:
             await interaction.response.edit_message(embed=embed, view=self)


    async def toggle_restriction(self, interaction: discord.Interaction):
        self.is_restricted = not self.is_restricted
        if not self.is_restricted:
            self.restricted_channels = []
        await self.update_message(interaction, status_message=f"Channel restriction {'enabled' if self.is_restricted else 'disabled'}.")

    async def add_channel(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddChannelModal(self))

    async def remove_channel_select(self, interaction: discord.Interaction):
         if not self.restricted_channels:
             await interaction.response.send_message("No channels to remove.", ephemeral=True)
             return

         options = []
         guild = interaction.guild
         for channel_id in self.restricted_channels:
             channel = guild.get_channel(channel_id)
             label = channel.name if channel else str(channel_id)
             options.append(discord.SelectOption(label=label, value=str(channel_id), description=f"ID: {channel_id}"))

         select = ui.Select(
             placeholder="Select channel(s) to remove...",
             options=options,
             min_values=1,
             max_values=len(options),
             custom_id="channel_remove_select"
         )
         select.callback = self.handle_remove_selection
         view = ui.View(timeout=180)
         view.add_item(select)
         await interaction.response.send_message("Select channels to remove from the allowed list:", view=view, ephemeral=True)

    async def handle_remove_selection(self, interaction: discord.Interaction):
         selected_ids = [int(val) for val in interaction.data['values']]
         removed_count = 0
         removed_mentions = []
         guild = interaction.guild

         new_list = []
         for cid in self.restricted_channels:
             if cid not in selected_ids:
                 new_list.append(cid)
             else:
                 removed_count += 1
                 channel = guild.get_channel(cid)
                 removed_mentions.append(channel.mention if channel else f"`{cid}`")

         self.restricted_channels = new_list

         await interaction.message.delete()
         await self.update_message(interaction, status_message=f"Removed {removed_count} channel(s): {', '.join(removed_mentions)}")


    async def save_configuration(self, interaction: discord.Interaction):
        try:
            await self.bot.db_client.save_config(self.guild_id, self.is_restricted, self.restricted_channels)
            self.bot.allowed_channels[self.guild_id] = self.restricted_channels if self.is_restricted else None
            self.original_state = (self.is_restricted, list(self.restricted_channels))
            self.saved_once = True
            await self.update_message(interaction, status_message="Configuration saved successfully!")

        except Exception as e:
             await interaction.response.send_message(f"Failed to save configuration: {e}", ephemeral=True)


    async def cancel_changes(self, interaction: discord.Interaction):
         self.is_restricted, self.restricted_channels = self.original_state
         self.restricted_channels = list(self.restricted_channels)
         await self.update_message(interaction, status_message="Changes cancelled.")


    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        print(f"OptionsView timed out for guild {self.guild_id}")


class OptionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="options",
        description="Configure Scriptly options for this server (Admin only)"
    )
    @discord.app_commands.checks.has_permissions(administrator=True)
    @discord.app_commands.guild_only()
    async def options(self, interaction: discord.Interaction):
        if not interaction.guild_id:
             await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
             return

        initial_channels = self.bot.allowed_channels.get(interaction.guild_id)
        view = OptionsView(self.bot, interaction.guild_id, initial_channels)
        embed = view._build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @options.error
    async def options_error(self, interaction: discord.Interaction, error):
        if isinstance(error, discord.app_commands.errors.MissingPermissions):
            await interaction.response.send_message("You need administrator permissions to use this command.", ephemeral=True)
        elif isinstance(error, discord.app_commands.errors.NoPrivateMessage):
             await interaction.response.send_message("This command cannot be used in direct messages.", ephemeral=True)
        else:
            print(f"Error in /options command: {error}")
            await interaction.response.send_message(f"An unexpected error occurred: {type(error).__name__}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(OptionsCog(bot))