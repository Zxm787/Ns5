import os
import sys
import json
import time
import discord
from utils.cloner import Cloner
from utils.panel import Panel, Panel_Run
from discord import Client, Intents
from rich.prompt import Prompt, Confirm
from time import sleep

with open("./utils/config.json", "r") as json_file:
    data = json.load(json_file)

os.system('cls' if os.name == 'nt' else 'clear')

# client سيتم إنشاؤه لاحقاً بعد قراءة إعدادات البروكسي
client = None


def build_client(config):
    """
    ينشئ عميل Discord مع دعم اختياري للبروكسي.
    يدعم: HTTP, HTTPS, SOCKS4, SOCKS5
    """
    proxy_cfg = config.get("proxy", {}) or {}

    # إذا كان البروكسي غير مفعل -> اتصال مباشر
    if not proxy_cfg.get("enabled"):
        print("> No proxy configured. Connecting directly...")
        return Client(intents=Intents.all())

    ptype = (proxy_cfg.get("type") or "http").lower().strip()
    host = (proxy_cfg.get("host") or "").strip()
    port = str(proxy_cfg.get("port") or "").strip()
    user = (proxy_cfg.get("username") or "").strip()
    password = (proxy_cfg.get("password") or "").strip()

    if not host or not port:
        print("> Proxy enabled but host/port missing. Connecting directly...")
        return Client(intents=Intents.all())

    print(f"> Using {ptype.upper()} proxy at {host}:{port}")

    # ------- SOCKS4 / SOCKS5 -------
    if ptype in ("socks5", "socks4"):
        try:
            from aiohttp_socks import ProxyConnector, ProxyType
        except ImportError:
            print("> aiohttp_socks غير مثبتة. نفّذ: pip install aiohttp_socks")
            print("> سيتم الاتصال مباشرة بدون بروكسي.")
            return Client(intents=Intents.all())

        connector = ProxyConnector(
            proxy_type=ProxyType.SOCKS5 if ptype == "socks5" else ProxyType.SOCKS4,
            host=host,
            port=int(port),
            username=user or None,
            password=password or None,
            rdns=True,  # مهم جداً لتفادي أخطاء SOCKS
        )
        return Client(intents=Intents.all(), connector=connector)

    # ------- HTTP / HTTPS -------
    try:
        from aiohttp import BasicAuth  # noqa: F401
    except ImportError:
        pass

    if user and password:
        proxy_url = f"{ptype}://{user}:{password}@{host}:{port}"
    else:
        proxy_url = f"{ptype}://{host}:{port}"

    return Client(intents=Intents.all(), proxy=proxy_url)


def clear(option=False):
    sleep(1)
    os.system('cls' if os.name == 'nt' else 'clear')
    if option:
        user = client.user
        guild = client.get_guild(int(INPUT_GUILD_ID))
        Panel_Run(guild, user)
    else:
        Panel()


async def clone_server():
    start_time = time.time()
    guild_from = client.get_guild(int(INPUT_GUILD_ID))
    print(" ")
    guild_to = client.get_guild(int(GUILD))

    # Edit the server name and icon
    await Cloner.guild_create(guild_to, guild_from)

    if data["copy_settings"]["roles"]:
        await Cloner.roles_create(guild_to, guild_from)
    if data["copy_settings"]["categories"]:
        await Cloner.categories_create(guild_to, guild_from)
    if data["copy_settings"]["channels"]:
        await Cloner.channels_create(guild_to, guild_from)
    if data["copy_settings"]["emojis"]:
        await Cloner.emojis_create(guild_to, guild_from)
    print("\n> Done Cloning Server in " +
          str(round(time.time() - start_time, 2)) + " seconds")


async def on_ready():
    clear(True)
    await clone_server()


class ClonerBot:

    def __init__(self):
        self.INPUT_GUILD_ID = None
        with open("./utils/config.json", "r") as json_file:
            self.data = json.load(json_file)

    def clear(self):
        sleep(1)
        os.system('cls' if os.name == 'nt' else 'clear')
        Panel()

    def edit_config(self, option, value, copy_settings=False):
        if copy_settings:
            self.data["copy_settings"][option] = value
        else:
            self.data[option] = value
        with open("./utils/config.json", "w") as json_file:
            json.dump(self.data, json_file, indent=4)

    def edit_settings_function(self):
        print("\nDo you want to copy:")
        categories = Confirm.ask("> Categories?")
        channels = Confirm.ask("> Channels?")
        roles = Confirm.ask("> Roles?")
        emojis = Confirm.ask("> Emojis?")
        for option in ["categories", "channels", "roles", "emojis"]:
            self.edit_config(option, locals()[option], copy_settings=True)

    def edit_proxy(self):
        """تهيئة البروكسي بشكل تفاعلي."""
        enable = Confirm.ask("\n> Do you want to use a proxy?")
        self.data.setdefault("proxy", {})
        self.data["proxy"]["enabled"] = enable

        if enable:
            ptype = Prompt.ask(
                "> Proxy type [http/https/socks5/socks4]",
                default=self.data["proxy"].get("type", "http"),
            ).lower().strip()

            host = Prompt.ask(
                "> Proxy host (e.g. 127.0.0.1)",
                default=self.data["proxy"].get("host", "") or "",
            ).strip()

            port = Prompt.ask(
                "> Proxy port (e.g. 8080)",
                default=str(self.data["proxy"].get("port", "") or ""),
            ).strip()

            user = Prompt.ask(
                "> Proxy username (leave empty if none)",
                default=self.data["proxy"].get("username", "") or "",
            ).strip()

            password = Prompt.ask(
                "> Proxy password (leave empty if none)",
                default=self.data["proxy"].get("password", "") or "",
            ).strip()

            self.data["proxy"].update({
                "type": ptype,
                "host": host,
                "port": port,
                "username": user,
                "password": password,
            })
        else:
            # تصفير الحقول عند التعطيل
            self.data["proxy"].update({
                "host": "",
                "port": "",
                "username": "",
                "password": "",
            })

        with open("./utils/config.json", "w") as json_file:
            json.dump(self.data, json_file, indent=4)

    def main(self):
        self.clear()
        if self.data["token"] == False:
            self.TOKEN = Prompt.ask("\n> Enter your Token")
            sleep(0.5)
        else:
            print("> Token Found")
        self.clear()

        edit_settings = Confirm.ask("\n> Do you want to edit the settings?")
        self.clear()
        if edit_settings:
            self.edit_settings_function()
        self.clear()

        # إعدادات البروكسي
        edit_proxy = Confirm.ask("\n> Do you want to edit proxy settings?")
        if edit_proxy:
            self.edit_proxy()
        self.clear()

        self.GUILD = Prompt.ask(
            '\n> Enter the Server ID you want to edit (Create a Server Manully)'
        )
        sleep(0.5)

        self.INPUT_GUILD_ID = Prompt.ask(
            "\n> Enter the Server ID you want to copy from"
        )
        sleep(0.5)

        return self.INPUT_GUILD_ID, self.TOKEN, self.GUILD


if __name__ == "__main__":
    INPUT_GUILD_ID, TOKEN, GUILD = ClonerBot().main()

    # إعادة قراءة الإعدادات في حال تم تعديلها للتو
    with open("./utils/config.json", "r") as json_file:
        data = json.load(json_file)

    # بناء العميل مع إعدادات البروكسي
    client = build_client(data)

    # ربط حدث on_ready بعد إنشاء العميل
    client.event(on_ready)

    try:
        client.run(TOKEN, bot=False)
        clear()
    except Exception as e:
        print(e)
        print("> Invalid Token or Proxy Error")
        data["token"] = False
        with open("./utils/config.json", "w") as json_file:
            json.dump(data, json_file, indent=4)