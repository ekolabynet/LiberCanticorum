#!/bin/bash
# Liber Canticorum – uruchamianie w macOS (dwuklik). Przy pierwszym starcie pobiera biblioteki.
cd "$(dirname "$0")/program" || exit 1
if ! command -v python3 >/dev/null; then
  echo "Potrzebny jest Python 3 – pobierz go z https://www.python.org/downloads/"; open https://www.python.org/downloads/; exit 1
fi
exec python3 uruchom.py "$@"
