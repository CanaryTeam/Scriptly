import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="scriptly")
    async def scriptly_help(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Scriptly AI Assistant",
            description=f"To talk to Scriptly, mention or ping {self.bot.user.mention} in your message.\nExample: `{self.bot.user.mention} How do I create a Discord bot?`",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Usage Limits",
            value="This service is being run 100% free. AI may not respond sometimes due to usage limits depending on demand.",
            inline=False
        )

        allowed_for_guild = self.bot.allowed_channels.get(ctx.guild.id) if ctx.guild else None

        if ctx.guild and allowed_for_guild:
            channel_mentions = []
            for ch_id in allowed_for_guild:
                channel = ctx.guild.get_channel(ch_id)
                if channel:
                    channel_mentions.append(channel.mention)

            if channel_mentions:
                embed.add_field(
                    name="Allowed Channels (This Server)",
                    value="Scriptly is only available in:\n" + "\n".join(channel_mentions),
                    inline=False
                )
            else:
                 embed.add_field(
                    name="Allowed Channels (This Server)",
                    value="Restriction is enabled, but no specific channels are set. Ask an admin to configure using `/options`.",
                    inline=False
                )
        else:
            embed.add_field(
                name="Allowed Channels (This Server)",
                value="Scriptly can be used in any channel on this server.",
                inline=False
            )

        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1357547210916626594/1362636885314244889/5erCemd.png?ex=68031dfe&is=6801cc7e&hm=e9ac9a92a1d134b342da3f9b15a890ccdd0e3473fdb0ff4ce5533dbdc532d9b9&")
        embed.set_footer(text="⚠️ Scriptly can make mistakes, don't rely on it for critical tasks.")
        await ctx.reply(f"{ctx.author.mention}", embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))