"""Run the bot's slash commands as prefix commands on discord.py 1.x.

macOS 10.12-10.14 installs use Python 3.7, which can only install discord.py 1.7.3. That
version has no slash commands (app_commands) and no buttons, dropdowns, or forms
(discord.ui). install() adds stand-ins so discordBot.py runs unchanged: attach() registers
every slash command as a prefix command ("fuzz!status", or "@Bot status"), and anything
that needs buttons or forms replies with a note instead.
"""
import inspect
import types
from typing import Optional

import discord
from discord.ext import commands

IS_LEGACY = int(discord.__version__.split(".")[0]) < 2
PREFIX = "fuzz!"
INTERACTIVE_UNAVAILABLE = (
    "ℹ️ Buttons, menus, and forms aren't available on this macOS version. "
    "Use the macro's GUI or the text commands in `" + PREFIX + "help` instead."
)


# --- app_commands stand-ins ---------------------------------------------------------

class Choice:
    def __init__(self, *, name, value):
        self.name = name
        self.value = value

    def __class_getitem__(cls, item):
        # allows annotations such as List[app_commands.Choice[str]]
        return cls


class CheckFailure(Exception):
    pass


def _ignore(**kwargs):
    return lambda func: func


def choices(**params):
    def decorator(func):
        func.__dict__.setdefault("legacy_choices", {}).update(params)
        return func
    return decorator


def check(predicate):
    def decorator(func):
        func.__dict__.setdefault("legacy_checks", []).append(predicate)
        return func
    return decorator


app_commands = types.SimpleNamespace(
    Choice=Choice,
    CheckFailure=CheckFailure,
    describe=_ignore,
    autocomplete=_ignore,
    choices=choices,
    check=check,
)


# --- discord.ui stand-ins -----------------------------------------------------------
# The settings panel classes subclass these at startup; they are never shown.

class _Component:
    def __init__(self, *args, **kwargs):
        self.children = []
        self.values = []

    def __init_subclass__(cls, **kwargs):
        # accepts class keywords such as Modal(title=...)
        super().__init_subclass__()

    def add_item(self, item):
        self.children.append(item)
        return self


class _AnyAttribute:
    """Stand-in for enums such as ButtonStyle: every attribute is None."""

    def __getattr__(self, name):
        return None


ui = types.SimpleNamespace(
    View=type("View", (_Component,), {}),
    Select=type("Select", (_Component,), {}),
    Button=type("Button", (_Component,), {}),
    Modal=type("Modal", (_Component,), {}),
    TextInput=type("TextInput", (_Component,), {}),
)


# --- Interaction adapter ------------------------------------------------------------

async def _send(ctx, content=None, *, embed=None, embeds=None, file=None, files=None, view=None, ephemeral=False, **_ignored):
    """Send like InteractionResponse.send_message, using DMs for ephemeral replies."""
    if view is not None:
        content = f"{content}\n{INTERACTIVE_UNAVAILABLE}" if content else INTERACTIVE_UNAVAILABLE
    extraEmbeds = []
    if embeds:
        embed, extraEmbeds = (embed, list(embeds)) if embed else (embeds[0], list(embeds[1:]))
    destination = ctx.author if ephemeral else ctx
    try:
        message = await destination.send(content, embed=embed, file=file, files=files)
        for extra in extraEmbeds:
            await destination.send(embed=extra)
    except discord.Forbidden:
        if not ephemeral:
            raise
        # DMs are closed; the reply is private, so don't post it in the channel
        return await ctx.send(f"{ctx.author.mention} ❌ Couldn't DM you the reply. Allow direct messages from server members and try again.")
    return message


class InteractionResponse:
    def __init__(self, ctx):
        self._ctx = ctx
        self._done = False

    def is_done(self):
        return self._done

    async def defer(self, *args, **kwargs):
        self._done = True
        await self._ctx.trigger_typing()

    async def send_message(self, content=None, **kwargs):
        self._done = True
        return await _send(self._ctx, content, **kwargs)

    async def edit_message(self, content=None, **kwargs):
        self._done = True
        return await _send(self._ctx, content, **kwargs)

    async def send_modal(self, modal):
        self._done = True
        await self._ctx.send(INTERACTIVE_UNAVAILABLE)


class Followup:
    def __init__(self, response):
        self._response = response

    async def send(self, content=None, **kwargs):
        # goes through send_message so discordBot's response footer patch applies here too
        return await self._response.send_message(content, **kwargs)


class Interaction:
    def __init__(self, ctx):
        self.user = ctx.author
        self.channel = ctx.channel
        self.channel_id = ctx.channel.id
        self.guild = ctx.guild
        self.client = ctx.bot
        self.message = ctx.message
        self.response = InteractionResponse(ctx)
        self.followup = Followup(self.response)


def install():
    """Add the 2.x names discordBot.py uses at import and definition time."""
    discord.Interaction = Interaction
    discord.InteractionResponse = InteractionResponse
    discord.ui = ui
    discord.SelectOption = _Component
    discord.ButtonStyle = _AnyAttribute()


# --- Command tree -------------------------------------------------------------------

def _resolveChoice(value, options):
    """Match typed text to a choice by value or name; returns None when nothing matches."""
    text = str(value).strip().lower()
    for option in options:
        if text in (str(option.value).lower(), str(option.name).lower()):
            return option.value
    return None


def _usage(name, params):
    parts = [PREFIX + name]
    for param in params:
        parts.append(f"<{param.name}>" if param.default is inspect.Parameter.empty else f"[{param.name}]")
    return f"`{' '.join(parts)}`"


class LegacyCommandTree:
    def __init__(self, bot):
        self.bot = bot
        self.errorHandler = None

    def error(self, handler):
        self.errorHandler = handler
        return handler

    async def sync(self):
        return []

    def command(self, *, name, description=""):
        def decorator(func):
            self.bot.add_command(self._prefixCommand(func, name, description))
            return func
        return decorator

    def _prefixCommand(self, func, name, description):
        params = list(inspect.signature(func).parameters.values())[1:]  # drop interaction
        # the last text parameter takes the rest of the message, so values can contain spaces
        if params and params[-1].annotation in (str, Optional[str]) and params[-1].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            params[-1] = params[-1].replace(kind=inspect.Parameter.KEYWORD_ONLY)
        signature = inspect.Signature(params)
        choiceOptions = getattr(func, "legacy_choices", {})
        checks = getattr(func, "legacy_checks", [])
        tree = self

        async def callback(ctx, *args, **kwargs):
            interaction = Interaction(ctx)
            try:
                for predicate in checks:
                    if not await predicate(interaction):
                        return
                bound = signature.bind(*args, **kwargs)
                for paramName, options in choiceOptions.items():
                    if paramName in bound.arguments:
                        value = _resolveChoice(bound.arguments[paramName], options)
                        if value is None:
                            allowed = ", ".join(f"`{option.value}`" for option in options)
                            await ctx.send(f"❌ `{paramName}` must be one of: {allowed}")
                            return
                        bound.arguments[paramName] = value
                await func(interaction, *bound.args, **bound.kwargs)
            except Exception as error:
                if tree.errorHandler is None:
                    raise
                await tree.errorHandler(interaction, error)

        callback.__signature__ = inspect.Signature(
            [inspect.Parameter("ctx", inspect.Parameter.POSITIONAL_OR_KEYWORD)] + params
        )
        return commands.Command(callback, name=name, help=description, usage=_usage(name, params), ignore_extra=False)


def attach(bot):
    """Give a discord.py 1.x bot a tree that registers prefix commands."""
    bot.tree = LegacyCommandTree(bot)
    # a mention always carries the message text, even without the message content intent
    bot.command_prefix = commands.when_mentioned_or(PREFIX)
    bot.remove_command("help")  # the bot's own help command replaces the built-in one

    @bot.listen()
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument, commands.TooManyArguments)):
            await ctx.send(f"❌ Usage: {ctx.command.usage}")
            return
        print(f"Discord command error: {error}")
