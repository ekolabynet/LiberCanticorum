#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Liber Canticorum – uruchamianie z terminala (to samo co dwuklik w „Liber Canticorum.desktop”).
#   ./start.sh               – uruchom (przy pierwszym starcie pobiera biblioteki)
#   ./start.sh --odtwarzacz  – doinstaluj wbudowany odtwarzacz YouTube (PySide6-Addons)
#   ./start.sh --skrot       – dodaj Liber Canticorum do menu programów (z ikoną)
cd "$(dirname "$0")"
exec python3 uruchom.py --konsola "$@"
