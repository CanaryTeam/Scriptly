import discord
from discord.ext import tasks
import logging
import asyncio 

logger = logging.getLogger(__name__)

@tasks.loop(seconds=60)
async def update_status_task(bot):
    await bot.wait_until_ready()

    if not bot.is_closed() and bot.ws:
        level = discord.Status.online
        text = "Low Usage"

        usage_count = getattr(bot, 'usage_count', 0)

        if usage_count >= 15:
            level = discord.Status.dnd
            text = "High Usage"
        elif usage_count >= 5:
            level = discord.Status.idle
            text = "Medium Usage"

        activity = discord.Activity(type=discord.ActivityType.watching, name=text)
        try:
            await bot.change_presence(status=level, activity=activity)
            logger.debug(f"Presence updated: {level}, Activity: {text}")
            bot.usage_count = 0
        except discord.errors.ConnectionClosed:
            logger.warning("Could not update presence: Connection was closed.")
        except Exception as e:
            logger.error(f"Error updating presence: {e}", exc_info=True)

    else:
        status = "closed" if bot.is_closed() else "websocket unavailable"
        logger.warning(f"Skipping presence update because bot status is: {status}")


def cancel_status_task():
    if update_status_task.is_running():
        logger.info("Cancelling status update task.")
        update_status_task.cancel()