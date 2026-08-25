#!/bin/bash
# Sobe o robô no testador visual com o preset de referência e abre o painel.
# Um clique: é o que se usa na apresentação.

MT5APP="/Applications/MetaTrader 5.app"
WINE="$MT5APP/Contents/SharedSupport/wine/bin/wine"
export WINEPREFIX="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5"
export DYLD_FALLBACK_LIBRARY_PATH="$MT5APP/Contents/SharedSupport/wine/lib/external:$MT5APP/Contents/SharedSupport/wine/lib:/usr/lib"
COMMON="$WINEPREFIX/drive_c/users/$USER/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
PAINEL="$HOME/DEV/RSI_Sniper_Instalacao/Scripts/rsi_panel.py"

echo "════════════════════════════════════════"
echo "  RSI SNIPER · demonstração"
echo "════════════════════════════════════════"

if pgrep -f "terminal64.exe" >/dev/null; then
  echo
  echo "  Já existe um MetaTrader aberto."
  read -p "  Fechar e subir a demonstração? [s/N] " r
  [[ "$r" =~ ^[SsYy]$ ]] || { echo "  Cancelado."; exit 0; }
  pkill -f "terminal64.exe"; sleep 2
fi

# Escreve a propria configuracao do teste. Assim o lancador nao depende de um
# arquivo que mora na pasta do MetaTrader e pode sumir numa reinstalacao.
CFG="$WINEPREFIX/drive_c/Program Files/MetaTrader 5/config/demonstracao.ini"
python3 - "$CFG" <<'PY'
import sys
ini = """[Tester]
Expert=MWM\\RSI_Sniper
ExpertParameters=referencia.set
Symbol=WIN$N
Period=H1
Model=1
Optimization=0
FromDate=2025.01.02
ToDate=2025.12.30
ForwardMode=0
Deposit=100000
Currency=BRL
Leverage=1:1
Visual=1
ShutdownTerminal=0
"""
open(sys.argv[1], "wb").write(b"\xff\xfe" + ini.encode("utf-16-le"))
PY

rm -f "$COMMON/rsi_data_BACKTEST.json"
echo
echo "  Subindo o robô no testador visual..."
"$WINE" "C:\\Program Files\\MetaTrader 5\\terminal64.exe" \
  "/config:C:\\Program Files\\MetaTrader 5\\config\\demonstracao.ini" >/dev/null 2>&1 &

# espera o robô publicar duas vezes: uma prova que subiu, duas que ficou
n=0; ant=""; fim=$((SECONDS+180))
while [ $SECONDS -lt $fim ] && [ $n -lt 2 ]; do
  if [ -f "$COMMON/rsi_data_BACKTEST.json" ]; then
    at=$(stat -f %m "$COMMON/rsi_data_BACKTEST.json" 2>/dev/null)
    [ "$at" != "$ant" ] && { ant="$at"; n=$((n+1)); }
  fi
  sleep 2
done

if [ $n -lt 2 ]; then
  echo
  echo "  O robô não começou a publicar."
  echo "  Confira se o MetaTrader está conectado (canto inferior direito)"
  echo "  e rode de novo."
  read -p "  Enter para fechar."
  exit 1
fi

echo "  Robô no ar. Abrindo o painel..."
PY=$(command -v python3)
exec "$PY" "$PAINEL"
