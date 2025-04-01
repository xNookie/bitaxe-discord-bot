# BitAxe Discord Bot

Ein Discord-Bot zur Überwachung von Bitaxe-Minern – zeigt Temperatur, Hashrate, Spannung, Strom, WLAN-Status u.v.m.

## Features

- Live-Dashboard mit automatisch aktualisierenden Embeds
- Statusabfragen via Discord-Befehle (!status, !power, !wifi etc.)
- Farbige Konsolenausgabe
- Automatische Warnmeldungen bei niedriger Hashrate, Fallback-Stratum usw.

## Setup

```bash
git clone https://github.com/DEINBENUTZERNAME/bitaxe-discord-bot.git
cd bitaxe-discord-bot
pip install -r requirements.txt
