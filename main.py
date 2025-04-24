import os
import io
import asyncio
import discord
from discord.ext import commands
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


ASCII_ART = r"""


 ________  ________  ________   ________  ________      ___    ___ 
|\   ____\|\   __  \|\   ___  \|\   __  \|\   __  \    |\  \  /  /|
\ \  \___|\ \  \|\  \ \  \\ \  \ \  \|\  \ \  \|\  \   \ \  \/  / /
 \ \  \    \ \   __  \ \  \\ \  \ \   __  \ \   _  _\   \ \    / / 
  \ \  \____\ \  \ \  \ \  \\ \  \ \  \ \  \ \  \\  \|   \/  /  /  
   \ \_______\ \__\ \__\ \__\\ \__\ \__\ \__\ \__\\ _\ __/  / /    
    \|_______|\|__|\|__|\|__| \|__|\|__|\|__|\|__|\|__|\___/ /     
                                                      \|___|/      

Developed by Canary Software
----------------------------------
"""

intents = discord.Intents.default()
intents.message_content = True # 
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
            self.logger.exception("CRITICAL: Failed to connect to DB or load initial configs. Check MONGO_URI and DB access.")

        self.logger.info("Loading extensions (cogs)...")
        commands_dir = "commands"
        for filename in os.listdir(commands_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                extension_name = f"{commands_dir}.{filename[:-3]}"
                try:
                    await self.load_extension(extension_name)
                    self.logger.info(f"Successfully loaded extension: {extension_name}")
                except commands.errors.NoEntryPointError:
                     self.logger.error(f"Extension {extension_name} has no 'async def setup(bot)' function.")
                except commands.errors.ExtensionNotFound:
                     self.logger.error(f"Extension {extension_name} could not be found.")
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
            self.logger.debug(f"Attempting to process prefix command: {message.content[:50]}")
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
                self.logger.debug(f"Ignoring mention in restricted channel {message.channel.id} in guild {message.guild.id}")
                try:
                    await message.reply(f"Sorry, I can only respond in specific channels in this server. Use `{self.command_prefix}scriptly` to see which.", delete_after=15, mention_author=False, allowed_mentions=discord.AllowedMentions.none())
                except discord.errors.Forbidden:
                    self.logger.warning(f"Cannot send restriction notice in channel {message.channel.id} (Forbidden).")
                except Exception as e:
                    self.logger.error(f"Error sending restriction notice: {e}")
                return

        self.usage_count += 1
        self.logger.info(f"AI mention detected from {message.author}. Usage count: {self.usage_count}")

        user_message = message.clean_content 
        bot_mention_pattern_nick = f'<@!{self.user.id}>'
        bot_mention_pattern_no_nick = f'<@{self.user.id}>' 
        user_message = user_message.replace(bot_mention_pattern_nick, '').replace(bot_mention_pattern_no_nick, '').strip()


        if not user_message:
            self.logger.info("Ignoring empty message after removing bot mention.")

        self.logger.info(f"Sending to AI: '{user_message[:100]}...'")
        async with message.channel.typing():
            try:
                ai_response = await get_ai_response(user_message)
            except Exception as e:
                self.logger.error(f"Exception during get_ai_response call: {e}")
                ai_response = f"Sorry, there was an internal error contacting the AI service ({type(e).__name__})."


        response_content = f"{ai_response}\n\n-# Scriptly can make mistakes, don't rely on it."

        try:
            if len(response_content) > 2000:
                self.logger.info("Response > 2000 chars, sending as file.")
                response_bytes = response_content.encode('utf-8')
                buffer = io.BytesIO(response_bytes)
                await message.reply("My response was too long, so I've attached it as a file:", file=discord.File(fp=buffer, filename="response.txt"), mention_author=False)
            else:
                await message.reply(response_content, mention_author=False, allowed_mentions=discord.AllowedMentions.none())
        except discord.errors.Forbidden:
            self.logger.warning(f"Cannot send message/reply in channel {message.channel.id} (Forbidden).")
        except discord.errors.HTTPException as e:
            self.logger.exception(f"Failed to send message (HTTP {e.status}, Code {e.code}): {e.text}")
            try:
                 await message.channel.send(f"{message.author.mention} Sorry, I encountered an error sending the response ({e.status}). Please try again later.", delete_after=20)
            except Exception:
                self.logger.warning(f"Also failed to send error message to channel {message.channel.id}.")
        except Exception as e:
             self.logger.exception(f"An unexpected error occurred during message reply.")
             try:
                  await message.channel.send(f"{message.author.mention} Sorry, an unexpected error occurred while replying.", delete_after=15)
             except Exception:
                  self.logger.warning(f"Also failed to send generic error message to channel {message.channel.id}.")


    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandNotFound):
            return

        log_message = f"Command Error in '{ctx.command.qualified_name if ctx.command else 'UnknownCmd'}'. User: {ctx.author}({ctx.author.id}). Guild: {ctx.guild}({ctx.guild.id}). Channel: {ctx.channel}({ctx.channel.id}). Error: {type(error).__name__}: {error}"
        original = getattr(error, 'original', None)
        if original:
            log_message += f" | Original: {type(original).__name__}: {original}"
            if isinstance(error, commands.CommandInvokeError):
                 self.logger.error(log_message, exc_info=original)
            else:
                 self.logger.error(log_message, exc_info=error)
        else:
            self.logger.error(log_message, exc_info=error)


        reply = None
        delete_after = 15 

        if isinstance(error, commands.errors.MissingRequiredArgument):
             reply = f"Oops! You missed the `{error.param.name}` argument. Use `{self.command_prefix}help {ctx.command.qualified_name}` for details."
        elif isinstance(error, commands.errors.BadArgument):
            reply = f"Looks like you provided an invalid argument. {error}"
        elif isinstance(error, commands.errors.UserInputError):
            reply = f"There was an issue with your input: {error}"
        elif isinstance(error, commands.errors.MissingPermissions):
             perms = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in error.missing_permissions)
             reply = f"You need the following permission(s) to use this command: {perms}"
        elif isinstance(error, commands.errors.BotMissingPermissions):
             perms = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in error.missing_permissions)
             reply = f"I can't do that because I'm missing permission(s): {perms}"
        elif isinstance(error, commands.errors.CommandOnCooldown):
             reply = f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds."
             delete_after = int(error.retry_after) + 1
        elif isinstance(error, commands.errors.NotOwner):
             reply = "This command can only be used by the bot owner."
        elif isinstance(error, commands.errors.CheckFailure): 
             reply = "You don't meet the requirements to use this command here."
        elif isinstance(error, commands.CommandInvokeError):
             reply = f"An internal error occurred while running the command. The issue has been logged."
        else:
             reply = "An unexpected error occurred while processing the command."

        if reply:
            try:
                await ctx.send(reply, delete_after=delete_after)
            except discord.errors.Forbidden:
                 self.logger.warning(f"Cannot send command error feedback in channel {ctx.channel.id} (Forbidden).")
            except Exception as e:
                self.logger.error(f"Failed to send command error feedback: {e}")


    async def close(self):
         self.logger.info("Initiating bot shutdown sequence...")
         cancel_status_task() 
         await super().close()
         if self.db_client:
             self.logger.info("Closing MongoDB connection...")
             try:
                self.db_client.client.close()
                self.logger.info("MongoDB connection closed.")
             except Exception as e:
                 self.logger.error(f"Error closing MongoDB connection: {e}")
         self.logger.info("Bot shutdown complete.")


if __name__ == "__main__":
    setup_logging()


    print(ASCII_ART)

    dotenv_path = '.env'
    if os.path.exists(dotenv_path):
        loaded = load_dotenv(dotenv_path=dotenv_path, override=True) 
        logging.info(f".env file loaded successfully: {loaded}")
    else:
        logging.warning(".env file not found. Relying on system environment variables.")

    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    MONGO_URI = os.getenv("MONGO_URI")
    GEMINI_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

    if not DISCORD_TOKEN:
        logging.critical("CRITICAL: DISCORD_TOKEN environment variable not set or found in .env. Bot cannot start.")
        sys.exit("DISCORD_TOKEN not set.")
    if not MONGO_URI:
        logging.critical("CRITICAL: MONGO_URI environment variable not set or found in .env. Database features will fail or bot may not start.")

    if not GEMINI_KEY:
         logging.warning("Warning: GOOGLE_GEMINI_API_KEY environment variable not set or found in .env. AI features will be disabled/fail.")
    logging.info("Essential environment variable checks passed (or warnings noted).")

    bot = ScriptlyBot()
    try:

        bot.run(
            DISCORD_TOKEN,
            reconnect=True,
            log_handler=None
        )
    except discord.errors.LoginFailure:
        logging.critical("CRITICAL: Login Failed - Incorrect Discord Token. Check your DISCORD_TOKEN in .env or environment.")
    except discord.errors.PrivilegedIntentsRequired:
         logging.critical("CRITICAL: Required Privileged Intents (Message Content likely) are not enabled for the bot in the Discord Developer Portal.")
    except Exception as e:
        logging.critical("CRITICAL: An unhandled exception occurred during bot execution.", exc_info=True)
    finally:
        logging.info("Bot process attempting to finish.")
        logging.shutdown()