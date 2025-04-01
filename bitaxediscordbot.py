import discord
import configparser
import os
import requests
import json
import pathlib
import matplotlib.pyplot as plt
import datetime
import io
import asyncio
import math

from discord.ext import commands
from colorama import init, Fore, Style
from zoneinfo import ZoneInfo 

init(autoreset=True)

# Konfiguration laden
config = configparser.ConfigParser()
config.read('config.ini')

console_interval = int(config['settings'].get('console_interval_sec', 30))

token = config['discord']['token']
channel_id = int(config['discord']['channel_id'])
BITAXE_API_URL = config['bitaxe']['api_url']
history_file = 'best_difficulty_history.json'  # Datei für die Historie

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

DASHBOARD_INTERVAL = int(config['settings'].get('dashboard_interval', 30))

# Live Dashboard
def fetch_bitaxe_data():
    return {
        "temp": 56.7,
        "hashRate": 375.32,
        "uptimeSeconds": 123456,
        "bestDiff": "568M",  # Beispielwert, z. B. "568M" – Steigt er, soll dies hervorgehoben werden
        "stratumURL": "pool.example.com",
        "coreVoltageActual": 1200,  # in mV
        "current": 1500,            # in mA
    }

# Funktion zum Parsen eines Best Diff-Strings (zum Vergleich)
def parse_best(best_str):
    try:
        # Suche nach Zahlen im String (z. B. "568" aus "568M")
        number_str = re.sub(r"[^\d.,]", "", best_str)
        number_str = number_str.replace(',', '.')
        return float(number_str)
    except Exception:
        return None

def generate_dashboard_embed(data, highlight_best=False):
    embed = discord.Embed(
        title="🚀 Live Dashboard",
        color=0x3498db,
        timestamp=datetime.datetime.utcnow()
    )
    
    # Hilfsfunktion für die Temperatur
    def format_temperature(temp):
        try:
            temp_val = float(temp)
        except Exception:
            return f"🌡 {temp} °C"
        if temp_val >= 60:
            emoji = "🔥"  # sehr heiß
        elif temp_val >= 55:
            emoji = "⚠️"  # Warnung
        else:
            emoji = "❄️"  # kühl
        return f"{emoji} {temp_val:.1f} °C"
    
    # Hilfsfunktion für die Hashrate
    def format_hashrate(hr):
        try:
            hr_val = float(hr)
        except Exception:
            return f"💪 {hr} MH/s"
        if hr_val >= 400:
            emoji = "💪"  # Top-Performance
        elif hr_val >= 350:
            emoji = "⚡"  # in Ordnung
        else:
            emoji = "🔥"  # niedrig
        return f"{emoji} {hr_val:.2f} MH/s"
    
    # Hilfsfunktion für die Uptime
    def format_uptime(uptime_sec):
        try:
            uptime_int = int(uptime_sec)
        except Exception:
            uptime_int = 0
        uptime_str = str(datetime.timedelta(seconds=uptime_int))
        return f"⌛ {uptime_str}"
    
    # Hilfsfunktion für Best Difficulty  
    def format_best_diff(best):
        if highlight_best:
            # Besonders hervorheben, wenn sich der Wert erhöht hat
            return f"✨🏆 {best}"
        else:
            return f"🏆 {best}"
    
    # Hilfsfunktion für Stratum mit unterschiedlichen Status-Emojis
    def format_stratum(stratum):
        if not stratum or stratum == "N/A":
            return f"🚫 N/A"
        else:
            emoji = "🏦" if "pool" in stratum.lower() else "🌐"
            return f"{emoji} {stratum}"
    
    # Hilfsfunktion für Chip Voltage (in mV -> V)
    def format_chip_voltage(voltage_actual):
        try:
            voltage_val = float(voltage_actual) / 1000.0
        except Exception:
            return "🔌 N/A"
        if voltage_val < 1.20:
            emoji = "🔻"  # zu niedrig
        elif voltage_val <= 1.30:
            emoji = "✅"  # ideal
        else:
            emoji = "🔺"  # zu hoch
        return f"{emoji} {voltage_val:.2f} V"
    
    # Hilfsfunktion für den Stromverbrauch (in mA -> A)
    def format_current(current):
        try:
            current_val = float(current) / 1000.0
        except Exception:
            return "🔋 N/A"
        if current_val >= 1.5:
            emoji = "⚡"  # hoher Verbrauch
        elif current_val >= 1.0:
            emoji = "🔋"  # normal
        else:
            emoji = "💡"  # niedrig, energieeffizient
        return f"{emoji} {current_val:.2f} A"
    
    if data:
        temp                = data.get("temp", "N/A")
        hr                  = data.get("hashRate", "N/A")
        uptime_seconds      = data.get("uptimeSeconds", 0)
        best                = data.get("bestDiff", "N/A")
        stratum             = data.get("stratumURL", "N/A")
        chip_voltage_actual = data.get("coreVoltageActual", "N/A")
        current_val         = data.get("current", "N/A")
        
        embed.add_field(name="Temperatur", value=format_temperature(temp), inline=True)
        embed.add_field(name="Hashrate", value=format_hashrate(hr), inline=True)
        embed.add_field(name="Uptime", value=format_uptime(uptime_seconds), inline=True)
        embed.add_field(name="Best Difficulty", value=format_best_diff(best), inline=True)
        embed.add_field(name="Stratum", value=format_stratum(stratum), inline=True)
        embed.add_field(name="Chip Voltage", value=format_chip_voltage(chip_voltage_actual), inline=True)
        embed.add_field(name="Stromverbrauch", value=format_current(current_val), inline=True)
    else:
        embed.add_field(name="Status", value="🚫 Keine Verbindung zur Bitaxe API.", inline=False)
    
    embed.set_footer(text=f"Dashboard aktualisiert sich alle {DASHBOARD_INTERVAL} Sekunden")
    return embed

# Dashboard-Command, der das Live-Dashboard anzeigt und regelmäßig aktualisiert
@bot.command(help="Zeigt ein Live-Dashboard mit kontinuierlichen Updates.")
async def dashboard(ctx):
    channel = ctx.channel
    timezone_str = config['settings'].get('timezone', 'Europe/Berlin')
    
    # Initiale Daten abrufen und Embed senden
    data = fetch_bitaxe_data()
    dashboard_message = await channel.send(embed=generate_dashboard_embed(data, highlight_best=False))
    
    # Den letzten Best Difficulty-Wert (als float) speichern
    last_best = parse_best(data.get("bestDiff", "N/A"))
    
    # Endlosschleife für regelmäßige Updates
    while True:
        data = fetch_bitaxe_data()
        new_best_str = data.get("bestDiff", "N/A")
        new_best_val = parse_best(new_best_str)
        
        # Überprüfen, ob sich der Best Difficulty-Wert erhöht hat
        if last_best is not None and new_best_val is not None and new_best_val > last_best:
            highlight = True
        else:
            highlight = False
        
        # Aktualisieren: Neuer Wert wird gespeichert
        if new_best_val is not None:
            last_best = new_best_val
        
        now = datetime.datetime.now(ZoneInfo(timezone_str))
        new_embed = generate_dashboard_embed(data, highlight_best=highlight)
        new_embed.timestamp = now
        try:
            await dashboard_message.edit(embed=new_embed)
        except Exception as e:
            print(f"Fehler beim Aktualisieren des Dashboards: {e}")
        await asyncio.sleep(DASHBOARD_INTERVAL)

# Optional: Im on_ready-Event kannst du auch das Dashboard automatisch an einem bestimmten Channel posten und anpinnen.
@bot.event
async def on_ready():
    print(f"{bot.user} ist jetzt online!")
    dashboard_channel_id = int(config['settings'].get("dashboard_channel_id", "123456789012345678"))
    channel = bot.get_channel(dashboard_channel_id)
    if channel is not None:
        embed = generate_dashboard_embed()
        dashboard_message = await channel.send(embed=embed)
        try:
            await dashboard_message.pin()
            print("Dashboard-Nachricht angepinnt.")
        except Exception as e:
            print(f"Fehler beim Anpinnen des Dashboards: {e}")
        # Starte den Update-Task für das Dashboard
        async def update_dashboard():
            while True:
                now = datetime.datetime.now(ZoneInfo(config['settings'].get("timezone", "Europe/Berlin")))
                new_embed = generate_dashboard_embed()
                new_embed.timestamp = now
                try:
                    await dashboard_message.edit(embed=new_embed)
                except Exception as e:
                    print(f"Fehler beim Aktualisieren des Dashboards: {e}")
                await asyncio.sleep(DASHBOARD_INTERVAL)
        bot.loop.create_task(update_dashboard())
    else:
        print("Dashboard-Channel nicht gefunden.")


# Historie laden, wenn die Datei existiert
def load_history():
    if os.path.exists(history_file):
        with open(history_file, 'r') as f:
            return json.load(f)
    return []

# Historie speichern
def save_history(history):
    with open(history_file, 'w') as f:
        json.dump(history, f)

# Funktion zum Abrufen der Bitaxe-Daten
def fetch_bitaxe_data():
    try:
        response = requests.get(BITAXE_API_URL, timeout=5)
        if response.status_code == 200 and response.text.strip():
            return response.json()
        else:
            return None
    except Exception:
        return None

@bot.event
async def on_ready():
    print(f"{Fore.CYAN}✅ Bot ist eingeloggt als {bot.user}{Style.RESET_ALL}")
    await send_startup_help()
    bot.loop.create_task(monitor_changes())

async def send_startup_help():
    await bot.wait_until_ready()
    channel = bot.get_channel(channel_id)
    if channel:
        categories = {
            "🟢 Status": ["status", "hashrate", "temp", "uptime"],
            "🔧 System": ["chip", "power", "fans", "version"],
            "🌐 Netzwerk": ["wifi"],
            "📋 Übersicht": ["info", "best", "stratum"]
        }
        help_text = (
            "🤖 **BitaxeDiscordBot ist online!** 🎉\n"
            "Hier sind deine wichtigsten Befehle – direkt einsatzbereit!\n\n"
            "📌 **Top-Befehl:**\n"
            "  🔹 `!dashboard` – zeigt ein live aktualisiertes Embed mit allen zentralen Systemwerten (wie Temperatur, Hashrate, Uptime, Best Difficulty, Stratum, Chip Voltage und Stromverbrauch) an\n\n"
            "📘 **Weitere Kategorien:**\n\n"
        )
        for category, commands_list in categories.items():
            help_text += f"{category}:\n"
            for name in commands_list:
                command = bot.get_command(name)
                if command and not command.hidden:
                    help_text += f"  🔹 `!{command.name}` – {command.help or 'Keine Beschreibung'}\n"
            help_text += "\n"
        await channel.send(help_text)

@bot.command(help="Zeigt den aktuellen Status des Bitaxe inkl. Temperatur, Uptime, Shares und freiem Speicher")
async def status(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler: Keine gültige Antwort von der Bitaxe API.")
        return

    temp = data.get("temp", "N/A")
    hr = data.get("hashRate", 0)
    uptime_sec = int(data.get("uptimeSeconds", 0))
    uptime = str(datetime.timedelta(seconds=uptime_sec))
    shares_accepted = data.get("sharesAccepted", 0)
    shares_rejected = data.get("sharesRejected", 0)
    free_heap = data.get("freeHeap", "N/A")

    # Temperatur-Icon
    if isinstance(temp, (int, float)):
        if temp >= 60:
            temp_icon = "🔴"
        elif temp >= 55:
            temp_icon = "🟡"
        else:
            temp_icon = "🟢"
    else:
        temp_icon = "❓"

    # Hashrate-Farbe
    if isinstance(hr, (int, float)):
        if hr >= 400:
            hr_icon = "🟢"
        elif hr >= 350:
            hr_icon = "🟡"
        else:
            hr_icon = "🔴"
    else:
        hr_icon = "❓"

    msg = f"""🟢 **Bitaxe Status**

🌡️ Temperatur: {temp_icon} {temp}°C
⚡ Hashrate: {hr_icon} {hr:.2f} MH/s
⏱️ Uptime: {uptime}
📈 Shares: ✅ {shares_accepted} / ❌ {shares_rejected}
💾 Freier Speicher: {free_heap} Bytes
"""
    await ctx.send(msg)

@bot.command(help="Zeigt die aktuelle Hashrate in MH/s")
async def hashrate(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler: Keine gültige Antwort von der Bitaxe API.")
        return
    hr = data.get("hashRate", 0)
    color = "🟢" if hr >= 400 else "🔴"
    await ctx.send(f"{color} Aktuelle Hashrate: {hr:.2f} MH/s")

@bot.command(help="Zeigt die aktuelle Temperatur und VRM-Temperatur")
async def temp(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler: Keine gültige Antwort von der Bitaxe API.")
        return
    temp = data.get("temp", "N/A")
    vr_temp = data.get("vrTemp", "N/A")
    await ctx.send(f"🌡️ Temperatur: {temp}°C | VRM: {vr_temp}°C")

@bot.command(help="Zeigt die aktuelle Uptime des Miners")
async def uptime(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler: Keine gültige Antwort von der Bitaxe API.")
        return
    uptime_sec = int(data.get("uptimeSeconds", 0))
    uptime_str = str(datetime.timedelta(seconds=uptime_sec))
    await ctx.send(f"⏱️ Uptime: {uptime_str}")

@bot.command(help="Zeigt das Chipmodell, die Frequenz und die Chip Voltage (2 Nachkommastellen, Aktuell/Soll)")
async def chip(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler: Keine gültige Antwort von der Bitaxe API.")
        return

    model = data.get("ASICModel", "N/A")
    freq = data.get("frequency", "N/A")
    
    try:
        # Umwandlung der Spannungswerte von mV in V
        voltage_actual = float(data.get("coreVoltageActual", "0")) / 1000.0
        voltage_set = float(data.get("coreVoltage", "0")) / 1000.0
        voltage_str = f"Aktuell: {voltage_actual:.2f}v | Soll: {voltage_set:.2f}v"
    except Exception:
        voltage_str = f"{data.get('coreVoltageActual', 'N/A')}/{data.get('coreVoltage', 'N/A')}v"
    
    # Erstelle ein Embed im gleichen Stil wie die anderen Befehle
    embed = discord.Embed(
        title="🔎 Chip-Informationen",
        color=0x3498db,
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Modell", value=model, inline=True)
    embed.add_field(name="Frequenz", value=f"{freq} MHz", inline=True)
    embed.add_field(name="Spannung", value=voltage_str, inline=False)
    
    # Thumbnail hinzufügen – Ersetze den Link durch ein passendes Discord-Icon, falls gewünscht.
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/810040487168608808.png")
    
    await ctx.send(embed=embed)


@bot.command(help="Zeigt Stromverbrauch, Spannung und Stromstärke sowie minPower und maxPower")
async def power(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler: Keine gültige Antwort von der Bitaxe API.")
        return

    # Leistung auslesen und formatieren
    raw_power = data.get("power", "N/A")
    raw_min_power = data.get("minPower", "N/A")
    raw_max_power = data.get("maxPower", "N/A")
    
    try:
        power_val = float(raw_power)
        min_power_val = float(raw_min_power)
        max_power_val = float(raw_max_power)
        power_str = f"{power_val:.2f} W ({min_power_val:.2f} - {max_power_val:.2f} W)"
    except Exception:
        power_str = f"{raw_power} W"

    # Spannung umrechnen: Aus mV in V
    raw_voltage = data.get("voltage", "N/A")
    try:
        voltage_val = float(raw_voltage) / 1000.0
        voltage_str = f"{voltage_val:.2f} V"
    except Exception:
        voltage_str = raw_voltage

    # Strom umrechnen: Aus mA in A
    raw_current = data.get("current", "N/A")
    try:
        current_val = float(raw_current) / 1000.0
        current_str = f"{current_val:.2f} A"
    except Exception:
        current_str = raw_current

    # Erstelle ein Embed im gleichen Stil wie beim !chip-Command
    embed = discord.Embed(
        title="🔌 Power-Informationen",
        color=0x3498db,
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Leistung", value=power_str, inline=False)
    embed.add_field(name="Spannung", value=voltage_str, inline=True)
    embed.add_field(name="Strom", value=current_str, inline=True)
    # Thumbnail: Hier wird ein Discord-eigenes Icon verwendet, ggf. anpassen
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/810040489041684746.png")
    
    await ctx.send(embed=embed)

@bot.command(help="Zeigt Lüftergeschwindigkeit, RPM und Auto-Fan-Status")
async def fans(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler: Keine gültige Antwort von der Bitaxe API.")
        return
    fanspeed = data.get("fanspeed", "N/A")
    fanrpm = data.get("fanrpm", "N/A")
    if isinstance(fanrpm, (int, float)):
        if fanrpm >= 5000:
            rpm_icon = "🟢"
        elif fanrpm >= 3000:
            rpm_icon = "🟡"
        else:
            rpm_icon = "🔴"
    else:
        rpm_icon = "❓"
    autofanspeed = data.get("autofanspeed", None)
    autofan_status = "✅ Auto-Fan aktiviert" if autofanspeed else "❌ Auto-Fan deaktiviert"
    if isinstance(fanspeed, (int, float)):
        if fanspeed >= 80:
            fan_icon = "🟢"
        elif fanspeed >= 50:
            fan_icon = "🟡"
        else:
            fan_icon = "🔴"
    else:
        fan_icon = "❓"
    await ctx.send(
        f"🌀 Lüfter: {fan_icon} {fanspeed}% ({rpm_icon} {fanrpm} RPM)\n"
        f"{autofan_status}"
    )

@bot.command(help="Zeigt WLAN-Status, SSID und IP-Adresse")
async def wifi(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler: Keine gültige Antwort von der Bitaxe API.")
        return
    ssid = data.get("ssid", "N/A")
    ip = data.get("hostip", "N/A")
    wifi_status = data.get("wifiStatus", "N/A")
    await ctx.send(f"📡 WLAN: {ssid} | IP: {ip} | Status: {wifi_status}")

@bot.command(help="Zeigt Firmware-Version, Partition und Reset-Grund")
async def version(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler: Keine gültige Antwort von der Bitaxe API.")
        return
    version = data.get("version", "N/A")
    partition = data.get("runningPartition", "N/A")
    reset_reason = data.get("lastResetReason", "N/A")
    await ctx.send(
        f"🧱 Firmware: {version} | Partition: {partition}\n"
        f"🔁 Letzter Reset: {reset_reason}"
    )

@bot.command(help="Zeigt alle verfügbaren Befehle sortiert nach Kategorien")
async def help(ctx):
    categories = {
        "🟢 Status": ["status", "hashrate", "temp", "uptime"],
        "🔧 System": ["chip", "power", "fans", "version"],
        "🌐 Netzwerk": ["wifi"],
        "📋 Übersicht": ["info", "best", "stratum"]
    }
    help_text = "📘 **Hilfe – Verfügbare Befehle:**\n\n"
    for category, commands_list in categories.items():
        help_text += f"{category}:\n"
        for name in commands_list:
            command = bot.get_command(name)
            if command and not command.hidden:
                help_text += f"  🔹 `!{command.name}` – {command.help or 'Keine Beschreibung'}\n"
        help_text += "\n"
    await ctx.send(help_text)

@bot.command(help="Zeigt Stratum- und Fallback-Stratum-Informationen")
async def stratum(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler beim Abrufen der Stratum-Daten.")
        return

    # Primäre Stratum-Daten
    url = data.get("stratumURL", "N/A")
    port = data.get("stratumPort", "N/A")
    user = data.get("stratumUser", "N/A")

    # Fallback-Daten
    fallback = data.get("isUsingFallbackStratum", False)
    fallback_url = data.get("fallbackStratumURL", "N/A")
    fallback_port = data.get("fallbackStratumPort", "N/A")
    fallback_user = data.get("fallbackStratumUser", "N/A")
    fallback_status = "✅ Aktiv" if fallback else "❌ Nicht aktiv"

    # Allgemeine Kennzeichnung, welcher Stratum aktuell aktiv ist
    active_stratum = "Fallback-Stratum" if fallback else "Primärer Stratum"

    message = (
        f"🌐 **Stratum-Info:**\n"
        f"• Aktiver Stratum: {active_stratum}\n\n"
        f"🔹 **Primärer Stratum:**\n"
        f"• URL: `{url}`\n"
        f"• Port: `{port}`\n"
        f"• User: `{user}`\n\n"
        f"🔄 **Fallback-Stratum:**\n"
        f"• URL: `{fallback_url}`\n"
        f"• Port: `{fallback_port}`\n"
        f"• User: `{fallback_user}`\n"
        f"• Fallback aktiv: {fallback_status}"
    )
    await ctx.send(message)

@bot.command(help="Zeigt den aktuellen besten Difficulty-Wert, den Session-Bestwert und eine Historie der Best Difficulties (höchste zuerst)")
async def best(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler: Keine gültige Antwort von der Bitaxe API.")
        return

    best_diff = data.get("bestDiff", "N/A")
    session = data.get("bestSessionDiff", "N/A")
    
    # Historie laden (aus der Datei best_difficulty_history.json)
    history = load_history()

    def parse_value(raw):
        """
        Konvertiert einen Wert wie "567M" oder "1234" in einen float.
        Unterstützt Suffixe: M (Millionen) und K (Tausend).
        """
        try:
            raw_str = str(raw).strip()
            multiplier = 1.0
            if raw_str.endswith("M"):
                multiplier = 1e6
                raw_str = raw_str[:-1]
            elif raw_str.endswith("K"):
                multiplier = 1e3
                raw_str = raw_str[:-1]
            return float(raw_str) * multiplier
        except Exception:
            return None

    numeric_best = parse_value(best_diff)
    # Neuen Historieneintrag anfügen, wenn ein gültiger Best-Wert vorliegt und sich
    # der Wert vom letzten gespeicherten unterscheidet.
    if best_diff != "N/A" and numeric_best is not None:
        if not history or (history and history[-1].get("best") != numeric_best):
            record = {
                "timestamp": datetime.datetime.now().isoformat(),
                "best": numeric_best
            }
            history.append(record)
            save_history(history)

    def format_number(num):
        """
        Gibt den vollständigen (ausgeschriebenen) Wert sowie eine abgekürzte Version zurück.
        Beispiel: 1234567 -> "1,234,567" und "1.23M"
        """
        full = f"{num:,.0f}"
        if num >= 1e6:
            abbr = f"{num/1e6:.2f}M"
        elif num >= 1e3:
            abbr = f"{num/1e3:.2f}K"
        else:
            abbr = f"{num:.2f}"
        return full, abbr

    # Sortiere die Historie nach dem Bestwert (höchste Werte zuerst)
    sorted_history = sorted(history, key=lambda rec: rec.get("best", 0), reverse=True)

    history_msg_lines = []
    for rec in sorted_history:
        ts = rec.get("timestamp", "Unbekannt")
        try:
            ts_formatted = datetime.datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            ts_formatted = ts
        best_val = rec.get("best")
        if isinstance(best_val, (int, float)):
            full_val, abbr_val = format_number(best_val)
            history_line = f"{ts_formatted} - {full_val} ({abbr_val})"
        else:
            history_line = f"{ts_formatted} - N/A"
        history_msg_lines.append(history_line)
    history_msg = "\n".join(history_msg_lines)

    msg = (
        f"🏆 Beste Difficulty: {best_diff} (Session: {session})\n\n"
        f"📜 Historie der Best Difficulties (höchste zuerst):\n{history_msg}"
    )
    await ctx.send(msg)

@bot.command(help="Zeigt eine kompakte Zusammenfassung wichtiger Werte")
async def info(ctx):
    data = fetch_bitaxe_data()
    if not data:
        await ctx.send("❌ Fehler: Keine gültige Antwort von der Bitaxe API.")
        return

    temp = data.get("temp", "N/A")
    hr = data.get("hashRate", 0)
    if isinstance(temp, (int, float)):
        if temp >= 60:
            temp_icon = "🔴"
        elif temp >= 55:
            temp_icon = "🟡"
        else:
            temp_icon = "🟢"
    else:
        temp_icon = "❓"

    if isinstance(hr, (int, float)):
        if hr >= 400:
            hr_icon = "🟢"
        elif hr >= 350:
            hr_icon = "🟡"
        else:
            hr_icon = "🔴"
    else:
        hr_icon = "❓"
    
    fanrpm = data.get("fanrpm", "N/A")
    if isinstance(fanrpm, (int, float)):
        if fanrpm >= 5000:
            rpm_icon = "🟢"
        elif fanrpm >= 3000:
            rpm_icon = "🟡"
        else:
            rpm_icon = "🔴"
    else:
        rpm_icon = "❓"

    msg = (
        f"📄 **Info NerdAxe**\n"
        f"Modell: {data.get('deviceModel')} ({data.get('ASICModel')})\n"
        f"Temp: {temp_icon} {temp}°C | HR: {hr_icon} {hr:.2f} MH/s\n"
        f"Lüfter: {rpm_icon} {fanrpm} RPM\n"
        f"IP: {data.get('hostip')} | WLAN: {data.get('ssid')}\n"
        f"Uptime: {str(datetime.timedelta(seconds=int(data.get('uptimeSeconds', 0))))}"
    )
    await ctx.send(msg)

async def log_to_console():
    await asyncio.sleep(1)
    # Lese die Zeitzone aus der Konfigurationsdatei, Standard: Europe/Berlin
    timezone_str = config['settings'].get('timezone', 'Europe/Berlin')
    while True:
        data = fetch_bitaxe_data()
        if data:
            temp = data.get("temp", "N/A")
            hr = data.get("hashRate", "N/A")
            uptime_sec = int(data.get("uptimeSeconds", 0))
            uptime = str(datetime.timedelta(seconds=uptime_sec))
            best = data.get("bestDiff", "N/A")
            stratum = data.get("stratumURL", "N/A")
            now = datetime.datetime.now(ZoneInfo(timezone_str)).strftime('%Y-%m-%d %H:%M:%S')

            # Bestimme Farbe und Emoji für die Hashrate
            if isinstance(hr, (int, float)):
                if hr >= 400:
                    hr_color = Fore.GREEN
                    hr_emoji = "💪"
                elif hr >= 350:
                    hr_color = Fore.YELLOW
                    hr_emoji = "⚡"
                else:
                    hr_color = Fore.RED
                    hr_emoji = "🔥"
            else:
                hr_color = Fore.RED
                hr_emoji = "❓"

            # Bestimme Farbe und Emoji für die Temperatur
            try:
                temp_float = float(temp)
            except Exception:
                temp_float = None
            if temp_float is not None:
                if temp_float >= 60:
                    temp_color = Fore.RED
                    temp_emoji = "🔥"
                elif temp_float >= 55:
                    temp_color = Fore.YELLOW
                    temp_emoji = "⚠️"
                else:
                    temp_color = Fore.GREEN
                    temp_emoji = "❄️"
            else:
                temp_color = Fore.WHITE
                temp_emoji = ""

            print(
                f"{Fore.BLUE}{now} [STATUS]{Style.RESET_ALL} "
                f"Temp: {temp_color}{temp_emoji} {temp}°C{Style.RESET_ALL} | "
                f"{hr_color}{hr_emoji} Hashrate: {hr} MH/s{Style.RESET_ALL} | "
                f"Uptime: {uptime} | BestDiff: {best} | Stratum: {stratum}"
            )
        else:
            print(f"{Fore.RED}[STATUS] 🚫 Keine Verbindung zur Bitaxe API.{Style.RESET_ALL}")
        
        await asyncio.sleep(int(config['settings'].get('console_interval_sec', 30)))

async def monitor_changes():
    # Starte den Konsolen-Logging-Task (der im Hintergrund läuft)
    bot.loop.create_task(log_to_console())
    
    # Hier folgt der Monitoring-Teil, der z. B. auf Änderungen reagiert und Nachrichten an Discord sendet.
    last_best = None
    while True:
        data = fetch_bitaxe_data()
        if data:
            best = data.get("bestDiff", "N/A")
            # Beispiel: Prüfe, ob sich der Best-Diff-Wert geändert hat
            if last_best is None:
                last_best = best
            elif best != last_best:
                channel = bot.get_channel(channel_id)
                await channel.send(f"🎉 **Neue Best Difficulty erreicht:** {best}")
                last_best = best
        else:
            # Hier könntest du ebenfalls Nachrichten senden, wenn z. B. keine Verbindung besteht
            pass

        # Warte 60 Sekunden, bevor du das nächste Mal prüfst
        await asyncio.sleep(60)


    # Hier könntest du den log_to_console Task starten oder weitere Logik unter monitor_changes hinzufügen.
    await log_to_console()  # Beispiel: direkt ausführen


    bot.loop.create_task(log_to_console())
    await bot.wait_until_ready()
    channel = bot.get_channel(channel_id)
    last_best = None
    fallback_announced = False
    unreachable_announced = False
    hashrate_zero_announced = False

    while True:
        data = fetch_bitaxe_data()
        if data:
            best = data.get("bestDiff")
            fallback = data.get("isUsingFallbackStratum", False)
            if best and best != last_best:
                await channel.send(f"🎉 **Neue Best Difficulty erreicht:** {best}")
                last_best = best
            if fallback and not fallback_announced:
                await channel.send("⚠️ **Achtung:** Der Miner verwendet derzeit den Fallback-Stratum!")
                fallback_announced = True
            if not fallback:
                fallback_announced = False
        else:
            if not unreachable_announced:
                await channel.send("🚫 **Bitaxe API nicht erreichbar!** Bitte Verbindung prüfen.")
                unreachable_announced = True
            hashrate_zero_announced = False

        if data:
            hr = data.get("hashRate", 0)
            if hr < 350 and not hashrate_zero_announced:
                await channel.send(f"⚠️ **Warnung:** Die Hashrate ist niedrig: {hr:.2f} MH/s!")
                hashrate_zero_announced = True
            elif hr >= 400 and hashrate_zero_announced:
                await channel.send(f"✅ **Entwarnung:** Hashrate wieder stabil bei {hr:.2f} MH/s.")
                hashrate_zero_announced = False
            unreachable_announced = False

        await asyncio.sleep(60)
      
if __name__ == "__main__":
    print(f"{Fore.YELLOW}🔁 Bot wird gestartet...{Style.RESET_ALL}")
    bot.run(token)