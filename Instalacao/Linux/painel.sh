#!/bin/bash
# RSI Sniper - Painel de Controle

echo "============================================================"
echo "  RSI SNIPER - Localizando Painel..."
echo "============================================================"
echo ""

# O prefixo Wine nao tem lugar fixo no Linux: ~/.wine e o padrao, o instalador
# oficial da MetaQuotes usa ~/.mt5, e PlayOnLinux/Lutris criam o seu. Procura em
# todos, primeiro na pasta de dados e depois no Program Files de cada um.
PANEL_FOUND=""
PREFIXOS="$HOME/.wine $HOME/.mt5 $HOME/.wine-mt5 $HOME/.local/share/wineprefixes/mt5"
for D in "$HOME/.local/share/lutris/prefixes"/* "$HOME/Games"/*; do
    [ -d "$D/drive_c" ] && PREFIXOS="$PREFIXOS $D"
done

for PREFIXO in $PREFIXOS; do
    [ -d "$PREFIXO/drive_c" ] || continue

    WINE_BASE="$PREFIXO/drive_c/users"
    if [ -d "$WINE_BASE" ]; then
        for USER_DIR in "$WINE_BASE"/*; do
            if [ -d "$USER_DIR" ]; then
                TERMINAL_PATH="$USER_DIR/AppData/Roaming/MetaQuotes/Terminal"
                if [ -d "$TERMINAL_PATH" ]; then
                    for INSTANCE in "$TERMINAL_PATH"/*; do
                        PANEL="$INSTANCE/MQL5/Include/MWM/rsi_panel.py"
                        if [ -f "$PANEL" ]; then
                            PANEL_DIR="$INSTANCE/MQL5/Include/MWM"
                            PANEL_FOUND="1"
                            break 3
                        fi
                    done
                fi
            fi
        done
    fi

    # Fallback: pasta do programa
    PROG_PANEL="$PREFIXO/drive_c/Program Files/MetaTrader 5/MQL5/Include/MWM/rsi_panel.py"
    if [ -f "$PROG_PANEL" ]; then
        PANEL_DIR="$PREFIXO/drive_c/Program Files/MetaTrader 5/MQL5/Include/MWM"
        PANEL_FOUND="1"
        break
    fi
done

if [ -n "$PANEL_FOUND" ]; then
    echo "Painel encontrado em:"
    echo "$PANEL_DIR"
    echo ""
    echo "Iniciando painel..."
    cd "$PANEL_DIR"
    # Procura um Python que realmente tenha a parte grafica (tkinter).
    # No macOS e comum ter varios Pythons e so alguns trazerem tkinter.
    PY=""
    for CAND in python3 python /usr/bin/python3 /opt/homebrew/bin/python3; do
        command -v "$CAND" >/dev/null 2>&1 || [ -x "$CAND" ] || continue
        if "$CAND" -c "import tkinter" >/dev/null 2>&1; then PY="$CAND"; break; fi
        [ -z "$PY" ] && PY="$CAND"
    done
    if [ -z "$PY" ]; then
        echo "Python nao encontrado. Instale o Python 3 e rode de novo."
        read -p "Pressione ENTER para fechar..."
        exit 1
    fi
    if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
        echo "Falta o tkinter (parte grafica do Python)."
        echo "  macOS: brew install python-tk"
        echo "  Linux: sudo apt install python3-tk"
        read -p "Pressione ENTER para fechar..."
        exit 1
    fi
    "$PY" -c "import customtkinter" >/dev/null 2>&1 || "$PY" -m pip install customtkinter
    # exec: o macOS/Dock associa o app ao PID deste script e so ativa a
    # janela de quem tem esse PID. Rodando o Python como filho, a janela
    # nasce num processo sem rosto e abre em branco. Com exec o Python
    # assume o PID do lancador e a janela recebe a ativacao e pinta.
    exec "$PY" rsi_panel.py
else
    echo ""
    echo "============================================================"
    echo "  ERRO: Painel nao encontrado!"
    echo "============================================================"
    echo ""
    echo "Execute o instalador primeiro."
    echo ""
    read -p "Pressione ENTER para fechar..."
fi
