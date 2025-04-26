import os
import io
import asyncio
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import logging
import sys
from database.mongo_client import get_db_client
from utils.ai_utils import get_ai_response
from utils.status_task import update_status_task, cancel_status_task

def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "scriptly.log")
    log_level = logging.INFO 

    log_format = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)-20s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='a')
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Error setting up file logging handler: {e}", file=sys.stderr)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.INFO)

    print(f"Logging setup complete. Level: {logging.getLevelName(log_level)}. Log file: {log_file}")
    logging.info("-------------------- Bot Start --------------------")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True    

class ScriptlyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=";", intents=intents)
        self.allowed_channels = {}
        self.usage_count = 0
        self.db_client = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def setup_hook(self):
        self.logger.info("Running setup_hook...")
        try:
            self.db_client = await get_db_client()
            self.allowed_channels = await self.db_client.load_all_configs()
            self.logger.info(f"Loaded configs for {len(self.allowed_channels)} guilds from DB.")
        except Exception as e:
            self.logger.exception("Failed to connect to DB or load initial configs.")

        self.logger.info("Loading extensions (cogs)...")
        commands_dir = "commands"
        for filename in os.listdir(commands_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                extension_name = f"{commands_dir}.{filename[:-3]}"
                try:
                    await self.load_extension(extension_name)
                    self.logger.info(f"Successfully loaded extension: {extension_name}")
                except Exception as e:
                    self.logger.exception(f"Failed to load extension {extension_name}.")

        self.logger.info("Syncing application (slash) commands...")
        try:
            synced = await self.tree.sync()
            self.logger.info(f"Synced {len(synced)} application command(s) globally.")
        except Exception as e:
            self.logger.exception("Error syncing application commands.")

        self.logger.info("setup_hook completed.")

    async def on_ready(self):
        self.logger.info(f'Logged in as {self.user.name} ({self.user.id})')
        self.logger.info(f'Connected to {len(self.guilds)} guilds.')
        self.logger.info('------ Bot is Ready ------')
        if not update_status_task.is_running():
             try:
                 update_status_task.start(self)
                 self.logger.info("Status update task started.")
             except RuntimeError as e:
                 self.logger.error(f"Could not start status task (already running or other issue?): {e}")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        is_guild = message.guild is not None
        is_mentioned = self.user in message.mentions

        if message.content.startswith(self.command_prefix):
            await self.process_commands(message)
            ctx = await self.get_context(message)
            if ctx.valid:
                self.logger.info(f"Processed command '{ctx.command.name}' by {message.author}")
                return

        if not is_mentioned:
            return

        if is_guild:
            guild_restrictions = self.allowed_channels.get(message.guild.id)
            if guild_restrictions is not None and message.channel.id not in guild_restrictions:
                await self.safe_reply(message, f"Sorry, I can only respond in specific channels in this server. Use `{self.command_prefix}scriptly` to see which.", delete_after=15)
                return

        self.usage_count += 1
        user_message = message.clean_content
        bot_mention_pattern_nick = f'<@!{self.user.id}>'
        bot_mention_pattern_no_nick = f'<@{self.user.id}>'
        user_message = user_message.replace(bot_mention_pattern_nick, '').replace(bot_mention_pattern_no_nick, '').strip()

        if not user_message:
            return

        async with message.channel.typing():
            try:
                ai_response = await get_ai_response(user_message)
            except Exception as e:
                self.logger.error(f"Exception during get_ai_response call: {e}")
                ai_response = f"Sorry, there was an internal error contacting the AI service ({type(e).__name__})."

        response_content = f"{ai_response}\n\n-# Scriptly can make mistakes, don't rely on it."
        await self.send_ai_response(message, response_content)

    async def send_ai_response(self, message, response_content):
        try:
            if len(response_content) > 2000:
                response_bytes = response_content.encode('utf-8')
                buffer = io.BytesIO(response_bytes)
                await message.reply("My response was too long, so I've attached it as a file:", file=discord.File(fp=buffer, filename="response.txt"), mention_author=False)
            else:
                await self.safe_reply(message, response_content, allowed_mentions=discord.AllowedMentions.none())
        except Exception as e:
            self.logger.exception(f"Error replying to message: {e}")

    async def safe_reply(self, message, content=None, file=None, **kwargs):
        try:
            await message.reply(content, file=file, **kwargs)
        except discord.errors.Forbidden:
            self.logger.warning(f"Cannot send message in channel {message.channel.id} (Forbidden).")
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandNotFound):
            return
        log_message = f"Error in '{ctx.command.qualified_name if ctx.command else 'UnknownCmd'}'. User: {ctx.author}({ctx.author.id}). Error: {type(error).__name__}: {error}"
        self.logger.error(log_message, exc_info=error)
        reply = self.get_error_message(error)
        if reply:
            try:
                await ctx.send(reply, delete_after=15)
            except Exception as e:
                self.logger.error(f"Failed to send command error feedback: {e}")

    def get_error_message(self, error):
        if isinstance(error, commands.errors.MissingRequiredArgument):
            return f"Missing argument `{error.param.name}`. Use `{self.command_prefix}help {error.param.name}` for details."
        if isinstance(error, commands.errors.BadArgument):
            return f"Invalid argument: {error}"
        if isinstance(error, commands.errors.UserInputError):
            return f"User input error: {error}"
        if isinstance(error, commands.errors.MissingPermissions):
            perms = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in error.missing_permissions)
            return f"You need the following permissions: {perms}"
        return "An unexpected error occurred."

    async def close(self):
        self.logger.info("Initiating bot shutdown...")
        cancel_status_task()
        await super().close()
        if self.db_client:
            try:
                self.db_client.client.close()
                self.logger.info("MongoDB connection closed.")
            except Exception as e:
                self.logger.error(f"Error closing MongoDB connection: {e}")
        self.logger.info("Bot shutdown complete.")

if __name__ == "__main__":
    setup_logging()
    dotenv_path = '.env'
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path, override=True)

    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    MONGO_URI = os.getenv("MONGO_URI")
    GEMINI_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

    if not DISCORD_TOKEN:
        sys.exit("DISCORD_TOKEN not set.")
    if not MONGO_URI:
        logging.warning("MONGO_URI not set.")
    if not GEMINI_KEY:
        logging.warning("GEMINI_KEY not set.")

    bot = ScriptlyBot()
    try:
        bot.run(DISCORD_TOKEN, reconnect=True)
    except discord.errors.LoginFailure:
        logging.critical("Login failed. Check DISCORD_TOKEN.")
    except discord.errors.PrivilegedIntentsRequired:
        logging.critical("Privileged intents required.")
    except Exception as e:
        logging.critical("Unhandled exception occurred.", exc_info=True)
    finally:
        logging.info("Bot process attempting to finish.")
        logging.shutdown()
