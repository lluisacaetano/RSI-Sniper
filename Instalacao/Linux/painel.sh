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
    # Escolhe o Python que abre o painel de verdade, nao so o primeiro que
    # tenha tkinter. Um Tk 8.5 (o Aqua antigo que a Apple ainda embarca em
    # /usr/bin/python3) cria a janela e nao desenha nada dentro: o painel
    # abre em branco. Caminhos absolutos primeiro, porque quem abre pelo
    # gerenciador de arquivos nao herda o PATH do shell.
    PY=""
    PY_TK_VELHO=""
    for CAND in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3 python /usr/bin/python3; do
        command -v "$CAND" >/dev/null 2>&1 || [ -x "$CAND" ] || continue
        TKVER="$("$CAND" -c 'import tkinter; print(tkinter.Tcl().call("info","patchlevel"))' 2>/dev/null)"
        [ -n "$TKVER" ] || continue
        case "$TKVER" in
            8.[0-5]*) [ -z "$PY_TK_VELHO" ] && PY_TK_VELHO="$CAND"; continue ;;
        esac
        PY="$CAND"
        break
    done
    if [ -z "$PY" ]; then
        if [ -n "$PY_TK_VELHO" ]; then
            echo "O Python encontrado ($PY_TK_VELHO) traz o Tk 8.5, que abre o painel em branco."
        else
            echo "Nao encontrei um Python 3 com a parte grafica (tkinter)."
        fi
        echo "  macOS: brew install python python-tk"
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
