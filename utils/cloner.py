import discord
from colorama import Fore, init, Style
import asyncio
import sys
import json
import aiohttp
import unicodedata

init(autoreset=True)

with open("./utils/config.json", "r") as json_file:
    data = json.load(json_file)
    logs_enabled = data["logs"]

# إعدادات إعادة المحاولة عند أخطاء الشبكة
MAX_RETRIES = 3
BASE_RETRY_DELAY = 2  # ثواني


# ----------------------------------------------------------------------
# أدوات المقارنة التامة 100% (Unicode-safe, case-sensitive)
# ----------------------------------------------------------------------
def _norm(name):
    """
    تطبيع Unicode بصيغة NFC.
    - يحافظ على حالة الأحرف (كبيرة/صغيرة).
    - يحافظ على الحروف العربية والعلامات الخاصة والمسافات.
    - يوحّد الأشكال المتكافئة (مثل أ المُدمج والمفكك).
    """
    if name is None:
        return ""
    return unicodedata.normalize("NFC", name)


def _exists(name, existing_set):
    """فحص وجود الاسم بمطابقة تامة وحساسة لحالة الأحرف."""
    return _norm(name) in existing_set


def clear_line(n=1):
    LINE_UP = '\033[1A'
    LINE_CLEAR = '\x1b[2K'
    for _ in range(n):
        print(LINE_UP, end=LINE_CLEAR)


def logs(message, type, number=None):
    if logs_enabled:
        log_types = {
            'add':     ('[+]',       Fore.GREEN),
            'delete':  ('[-]',       Fore.RED),
            'warning': ('[WARNING]', Fore.YELLOW),
            'error':   ('[ERROR]',   Fore.RED),
            'skip':    ('[SKIP]',    Fore.CYAN),
            'retry':   ('[RETRY]',   Fore.MAGENTA),
            'info':    ('[INFO]',    Fore.BLUE),
        }
        prefix, color = log_types.get(type, ('[?]', Fore.RESET))

        if number is not None:
            print(f" {color}{prefix}{Style.RESET_ALL} {message}")
        else:
            print(f" {color}{prefix}{Style.RESET_ALL} {message}")
            clear_line()


class Cloner:

    # ------------------------------------------------------------------
    # تنفيذ عملية بأمان مع إعادة المحاولة عند أخطاء الشبكة
    # ------------------------------------------------------------------
    @staticmethod
    async def _safe(op_factory, description, max_retries=MAX_RETRIES):
        for attempt in range(1, max_retries + 1):
            try:
                return await op_factory()

            except discord.Forbidden as e:
                logs(f"Forbidden ({description}): {e}", 'error')
                return None

            except discord.HTTPException as e:
                status = getattr(e, 'status', None)
                if status == 429:
                    retry_after = getattr(e, 'retry_after', 2) or 2
                    logs(f"Rate limited on {description}, waiting {retry_after}s", 'warning')
                    await asyncio.sleep(retry_after)
                    continue
                logs(f"HTTP {status} ({description}): {e}", 'error')
                return None

            except (aiohttp.ClientOSError, aiohttp.ClientError,
                    asyncio.TimeoutError, ConnectionError, OSError) as e:
                if attempt < max_retries:
                    wait = BASE_RETRY_DELAY * attempt
                    logs(f"Network error ({attempt}/{max_retries}) on {description}: {e} "
                         f"→ retry in {wait}s", 'retry')
                    await asyncio.sleep(wait)
                else:
                    logs(f"Network error after {max_retries} attempts on {description}: {e}", 'error')
                    return None

            except Exception as e:
                logs(f"Unexpected error ({description}): {type(e).__name__}: {e}", 'error')
                return None

        return None

    # ------------------------------------------------------------------
    # نسخ بيانات السيرفر الأساسية
    # ------------------------------------------------------------------
    @staticmethod
    async def guild_create(guild_to: discord.Guild, guild_from: discord.Guild):
        try:
            icon_image = None
            try:
                icon_image = await guild_from.icon_url_as(format='jpg').read()
            except Exception as e:
                logs(f"Can't read icon image from {guild_from.name}: {e}", 'warning')

            # مقارنة الاسم بمطابقة تامة 100%
            if _norm(guild_to.name) == _norm(guild_from.name):
                logs(f"Guild name already matches exactly: {guild_to.name}", 'skip')
            else:
                await Cloner._safe(
                    lambda: guild_to.edit(name=guild_from.name),
                    f"rename guild to {guild_from.name}"
                )

            if icon_image is not None:
                await Cloner._safe(
                    lambda: guild_to.edit(icon=icon_image),
                    "change guild icon"
                )
                logs(f"Guild icon updated: {guild_to.name}", 'add')

            logs(f"Cloned server: {guild_to.name}", 'add', True)

        except Exception as e:
            logs(f"guild_create failed: {e}", 'error')

    # ------------------------------------------------------------------
    # نسخ الرتب — مطابقة تامة 100%
    # ------------------------------------------------------------------
    @staticmethod
    async def roles_create(guild_to: discord.Guild, guild_from: discord.Guild):
        # نطبّع أسماء الرتب الموجودة في الهدف
        existing_names = {_norm(r.name) for r in guild_to.roles}

        roles = [r for r in guild_from.roles if r.name != "@everyone"]
        roles.reverse()

        created = skipped = failed = 0

        for role in roles:
            try:
                if _exists(role.name, existing_names):
                    logs(f"Role already exists (exact match), skipping: {role.name}", 'skip')
                    skipped += 1
                    continue

                result = await Cloner._safe(
                    lambda r=role: guild_to.create_role(
                        name=r.name,
                        permissions=r.permissions,
                        colour=r.colour,
                        hoist=r.hoist,
                        mentionable=r.mentionable,
                    ),
                    f"create role {role.name}"
                )

                if result is not None:
                    created += 1
                    existing_names.add(_norm(role.name))
                    logs(f"Created Role {role.name}", 'add')
                else:
                    failed += 1

                await asyncio.sleep(0.3)

            except Exception as e:
                failed += 1
                logs(f"Unexpected error in role {getattr(role, 'name', '?')}: {e}", 'error')
                continue

        logs(f"Roles → created: {created}, skipped: {skipped}, failed: {failed}", 'add', True)

    # ------------------------------------------------------------------
    # نسخ الفئات — مطابقة تامة 100%
    # ------------------------------------------------------------------
    @staticmethod
    async def categories_create(guild_to: discord.Guild, guild_from: discord.Guild):
        existing_names = {_norm(c.name) for c in guild_to.categories}

        created = skipped = failed = 0

        for channel in guild_from.categories:
            try:
                if _exists(channel.name, existing_names):
                    logs(f"Category already exists (exact match), skipping: {channel.name}", 'skip')
                    skipped += 1
                    continue

                overwrites_to = {}
                for key, value in channel.overwrites.items():
                    role = discord.utils.get(guild_to.roles, name=getattr(key, 'name', None))
                    if role is not None:
                        overwrites_to[role] = value

                new_channel = await Cloner._safe(
                    lambda c=channel, o=overwrites_to: guild_to.create_category(
                        name=c.name, overwrites=o
                    ),
                    f"create category {channel.name}"
                )

                if new_channel is not None:
                    await Cloner._safe(
                        lambda nc=new_channel, pos=channel.position: nc.edit(position=pos),
                        f"reposition category {channel.name}"
                    )
                    created += 1
                    existing_names.add(_norm(channel.name))
                    logs(f"Created Category: {channel.name}", 'add')
                else:
                    failed += 1

                await asyncio.sleep(0.3)

            except Exception as e:
                failed += 1
                logs(f"Unexpected error in category {getattr(channel, 'name', '?')}: {e}", 'error')
                continue

        logs(f"Categories → created: {created}, skipped: {skipped}, failed: {failed}", 'add', True)

    # ------------------------------------------------------------------
    # نسخ القنوات — مطابقة تامة 100% (حساسة لحالة الأحرف)
    # ------------------------------------------------------------------
    @staticmethod
    async def channels_create(guild_to: discord.Guild, guild_from: discord.Guild):
        # ⚠️ ملاحظة: تم إزالة .lower() لتحقيق مطابقة 100%
        # Discord نفسه يخزّن أسماء القنوات بحروف صغيرة والمسافات →
        # لذا الأسماء القادمة من API ستكون موحّدة، والمقارنة التامة صحيحة.
        existing_text = {_norm(c.name) for c in guild_to.text_channels}
        existing_voice = {_norm(c.name) for c in guild_to.voice_channels}

        channels = list(guild_from.text_channels) + list(guild_from.voice_channels)

        created = skipped = failed = 0

        for channel in channels:
            try:
                is_text = isinstance(channel, discord.TextChannel)
                existing_set = existing_text if is_text else existing_voice

                if _exists(channel.name, existing_set):
                    logs(f"Channel already exists (exact match), skipping: {channel.name}", 'skip')
                    skipped += 1
                    continue

                category = None
                if channel.category is not None:
                    category = discord.utils.get(guild_to.categories, name=channel.category.name)

                overwrites_to = {}
                for key, value in channel.overwrites.items():
                    role = discord.utils.get(guild_to.roles, name=getattr(key, 'name', None))
                    if role is not None:
                        overwrites_to[role] = value

                create_fn = guild_to.create_text_channel if is_text else guild_to.create_voice_channel

                new_channel = await Cloner._safe(
                    lambda fn=create_fn, c=channel, o=overwrites_to: fn(
                        name=c.name, overwrites=o, position=c.position
                    ),
                    f"create channel {channel.name}"
                )

                if new_channel is not None:
                    if category is not None:
                        await Cloner._safe(
                            lambda nc=new_channel, cat=category: nc.edit(category=cat),
                            f"move channel {channel.name} to category"
                        )
                    created += 1
                    existing_set.add(_norm(channel.name))
                    kind = "Text" if is_text else "Voice"
                    logs(f"Created {kind} Channel: {channel.name}", 'add')
                else:
                    failed += 1

                await asyncio.sleep(0.3)

            except Exception as e:
                failed += 1
                logs(f"Unexpected error in channel {getattr(channel, 'name', '?')}: {e}", 'error')
                continue

        logs(f"Channels → created: {created}, skipped: {skipped}, failed: {failed}", 'add', True)

    # ------------------------------------------------------------------
    # نسخ الإيموجي — مطابقة تامة 100%
    # ------------------------------------------------------------------
    @staticmethod
    async def emojis_create(guild_to: discord.Guild, guild_from: discord.Guild):
        existing_names = {_norm(e.name) for e in guild_to.emojis}

        created = skipped = failed = 0

        for emoji in guild_from.emojis:
            try:
                if _exists(emoji.name, existing_names):
                    logs(f"Emoji already exists (exact match), skipping: {emoji.name}", 'skip')
                    skipped += 1
                    continue

                emoji_image = await emoji.url.read()

                result = await Cloner._safe(
                    lambda e=emoji, img=emoji_image: guild_to.create_custom_emoji(
                        name=e.name, image=img
                    ),
                    f"create emoji {emoji.name}"
                )

                if result is not None:
                    created += 1
                    existing_names.add(_norm(emoji.name))
                    logs(f"Created Emoji {emoji.name}", 'add')
                else:
                    failed += 1

                await asyncio.sleep(0.3)

            except Exception as e:
                failed += 1
                logs(f"Unexpected error in emoji {getattr(emoji, 'name', '?')}: {e}", 'error')
                continue

        logs(f"Emojis → created: {created}, skipped: {skipped}, failed: {failed}", 'add', True)
