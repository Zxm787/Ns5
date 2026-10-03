from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.style import Style
from rich.panel import Panel as RichPanel
import json


def _proxy_status_text(data):
    """يُرجع نصاً مُنسقاً لحالة البروكسي."""
    proxy = data.get("proxy", {}) or {}
    if not proxy.get("enabled"):
        return Text("OFF", style=Style(color="red", bold=True))
    host = proxy.get("host") or "?"
    port = proxy.get("port") or "?"
    ptype = (proxy.get("type") or "http").upper()
    return Text(f"ON ({ptype} {host}:{port})",
                style=Style(color="green", bold=True))


def Panel():
    with open("./utils/config.json", "r") as json_file:
        data = json.load(json_file)
    print(" ")

    on_style = Style(color="green", bold=True)
    off_style = Style(color="red", bold=True)

    table = Table(title="Discord Server Cloner", show_header=True, header_style="bold")
    table.add_column("Setting", style="cyan", no_wrap=True, width=30)
    table.add_column("Status", justify="center", width=25)

    for setting, status in data["copy_settings"].items():
        table.add_row(
            setting.capitalize(),
            Text("ON" if status else "OFF", style=on_style if status else off_style),
        )

    # صف البروكسي
    table.add_row("Proxy", _proxy_status_text(data))

    console = Console()
    console.print(table)

    paragraph = """Discord has removed the functionality for bots to create a server automatically. You will have to create a server manually and provide the server ID and the server you want to clone."""
    console.print(RichPanel(paragraph, style="bold blue", width=47))

    version = "2.0.2"
    console.print(RichPanel(f"Version: {version}", style="bold magenta", width=47))


def Panel_Run(guild, user):
    with open("./utils/config.json", "r") as json_file:
        data = json.load(json_file)
    print(" ")

    on_style = Style(color="green", bold=True)
    off_style = Style(color="red", bold=True)

    table = Table(title="Discord Server Cloner", show_header=True, header_style="bold")
    table.add_column("Cloner is Running...", style="cyan", no_wrap=True, width=30)
    table.add_column("Status", justify="center", width=25)

    for setting, status in data["copy_settings"].items():
        table.add_row(
            setting.capitalize(),
            Text("ON" if status else "OFF", style=on_style if status else off_style),
        )

    table.add_row("Proxy", _proxy_status_text(data))

    footer = Table(show_header=False, header_style="bold", show_lines=False, width=47)
    footer.add_column(justify="center")
    footer.add_row(f"[bold magenta]Server ID: [green]{guild}")
    footer.add_row(f"[bold magenta]Logged in as: [green]{user}")

    console = Console()
    console.print(table)
    console.print(footer)

    paragraph = """Discord has removed the functionality for bots to create a server automatically. You will have to create a server manually and provide the server ID and the server you want to clone."""
    console.print(RichPanel(paragraph, style="bold blue", width=47))

    version = "2.0.2"
    console.print(RichPanel(f"Version: {version}", style="bold magenta", width=47))