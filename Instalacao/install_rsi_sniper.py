#!/usr/bin/env python3
"""
RSI SNIPER - Instalador Automático Multiplataforma
Detecta a pasta de DADOS do MetaTrader 5 (onde fica o MQL5)
Compatível: Windows, macOS (Wine), Linux (Wine)
"""

import os
import sys
import platform
from pathlib import Path
import shutil
import subprocess

class RSISniperInstaller:
    def __init__(self):
        self.sistema = platform.system()
        self.mql5_path = None  # Pasta MQL5 de dados (não a do programa!)
        self.arquivos_instalados = []

    def encontrar_pastas_mql5(self):
        """
        Encontra todas as pastas MQL5 de dados do MetaTrader 5.

        IMPORTANTE: O MT5 tem duas pastas diferentes:
        - Pasta do PROGRAMA: C:/Program Files/MetaTrader 5/ (onde esta o .exe)
        - Pasta de DADOS: %APPDATA%/MetaQuotes/Terminal/<ID>/MQL5/ (onde ficam os EAs)

        Esta funcao procura a pasta de DADOS, que e onde devemos instalar.
        """
        home = Path.home()
        pastas_encontradas = []

        if self.sistema == "Darwin":  # macOS
            # Wine prefix padrão do MT5 no macOS
            wine_appdata = home / "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users"

            # Procura em todas as pastas de usuário do Wine
            if wine_appdata.exists():
                for user_folder in wine_appdata.iterdir():
                    if user_folder.is_dir():
                        terminal_path = user_folder / "AppData/Roaming/MetaQuotes/Terminal"
                        if terminal_path.exists():
                            for instance in terminal_path.iterdir():
                                mql5_path = instance / "MQL5"
                                try:
                                    if mql5_path.exists() and instance.name != "Common":
                                        pastas_encontradas.append(mql5_path)
                                except PermissionError:
                                    pass

            # Fallback: pasta do programa (alguns setups antigos)
            programa_path = home / "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5"
            if programa_path.exists() and programa_path not in pastas_encontradas:
                pastas_encontradas.append(programa_path)

        elif self.sistema == "Windows":
            # Pasta de dados do Windows
            appdata = Path(os.environ.get("APPDATA", ""))
            terminal_path = appdata / "MetaQuotes/Terminal"

            if terminal_path.exists():
                for instance in terminal_path.iterdir():
                    mql5_path = instance / "MQL5"
                    try:
                        if mql5_path.exists() and instance.name != "Common":
                            pastas_encontradas.append(mql5_path)
                    except PermissionError:
                        # Ignora pastas sem permissao de acesso
                        pass

            # Fallback: pasta do programa
            for prog_path in [Path("C:/Program Files/MetaTrader 5/MQL5"),
                              Path("C:/Program Files (x86)/MetaTrader 5/MQL5")]:
                if prog_path.exists() and prog_path not in pastas_encontradas:
                    pastas_encontradas.append(prog_path)

        else:  # Linux
            # No Linux o prefixo Wine nao tem lugar fixo: ~/.wine e o padrao,
            # mas o instalador oficial da MetaQuotes usa ~/.mt5, e PlayOnLinux
            # e Lutris criam o seu. Varremos todos os que existirem, em vez de
            # assumir um so como o macOS pode fazer.
            prefixos = [
                home / ".wine",
                home / ".mt5",
                home / ".wine-mt5",
                home / ".local/share/wineprefixes/mt5",
                home / "PlayOnLinux's virtual drives/MetaTrader5",
            ]
            for extra in (home / ".local/share/lutris/prefixes",
                          home / "Games"):
                try:
                    if extra.is_dir():
                        prefixos.extend(d for d in extra.iterdir() if d.is_dir())
                except (PermissionError, OSError):
                    pass

            vistos = set()
            for prefixo in prefixos:
                drive_c = prefixo / "drive_c"
                if not drive_c.is_dir() or drive_c in vistos:
                    continue
                vistos.add(drive_c)

                wine_appdata = drive_c / "users"
                if wine_appdata.exists():
                    try:
                        usuarios = list(wine_appdata.iterdir())
                    except (PermissionError, OSError):
                        usuarios = []
                    for user_folder in usuarios:
                        if user_folder.is_dir():
                            terminal_path = user_folder / "AppData/Roaming/MetaQuotes/Terminal"
                            if terminal_path.exists():
                                for instance in terminal_path.iterdir():
                                    mql5_path = instance / "MQL5"
                                    try:
                                        if mql5_path.exists() and instance.name != "Common":
                                            if mql5_path not in pastas_encontradas:
                                                pastas_encontradas.append(mql5_path)
                                    except PermissionError:
                                        pass

                # Fallback: pasta do programa. O macOS e o Windows ja faziam
                # isto; sem ele, uma instalacao que ficou so em Program Files
                # some do radar. E o caso mais comum do que parece.
                programa_path = drive_c / "Program Files/MetaTrader 5/MQL5"
                if programa_path.exists() and programa_path not in pastas_encontradas:
                    pastas_encontradas.append(programa_path)

        return pastas_encontradas

    def detectar_mt5(self):
        """Detecta automaticamente a pasta MQL5 do MetaTrader 5"""
        print(f"\n{'='*60}")
        print(f"  🎯 RSI SNIPER - Instalador ({self.sistema})")
        print(f"{'='*60}\n")
        print("🔍 Procurando pasta de dados do MetaTrader 5...\n")

        pastas = self.encontrar_pastas_mql5()

        if not pastas:
            print("❌ Nenhuma instalacao do MetaTrader 5 encontrada.\n")
            print("Deseja informar o caminho manualmente? (s/n): ", end="")
            resp = input().strip().lower()
            if resp == 's' or resp == 'sim':
                return self._solicitar_caminho_manual()
            else:
                print("\n")
                self._mostrar_instrucoes_manuais()
                return False

        if len(pastas) == 1:
            self.mql5_path = pastas[0]
            print(f"✅ Pasta MQL5 encontrada:\n   {self.mql5_path}\n")
            return True

        # Múltiplas instalações - deixa o usuário escolher
        print(f"📂 {len(pastas)} instalação(ões) encontrada(s):\n")
        for i, pasta in enumerate(pastas, 1):
            # Mostra o ID da instância para ajudar a identificar
            instance_id = pasta.parent.name[:8] if len(pasta.parent.name) > 8 else pasta.parent.name
            print(f"   [{i}] {pasta}")
            print(f"       (ID: {instance_id}...)\n")

        while True:
            try:
                escolha = input(f"Escolha uma opção (1-{len(pastas)}): ").strip()
                idx = int(escolha) - 1
                if 0 <= idx < len(pastas):
                    self.mql5_path = pastas[idx]
                    print(f"\n✅ Usando: {self.mql5_path}\n")
                    return True
                else:
                    print("❌ Opção inválida. Tente novamente.")
            except ValueError:
                print("❌ Digite um número válido.")

    def _solicitar_caminho_manual(self):
        """Solicita o caminho manualmente"""
        print("📝 Por favor, informe o caminho da pasta MQL5 manualmente.")
        print("   (É a pasta que contém Experts, Include, Indicators, etc.)\n")

        if self.sistema == "Windows":
            print("   Exemplo: C:/Users/SeuUsuario/AppData/Roaming/MetaQuotes/Terminal/XXXXX/MQL5")
        elif self.sistema == "Darwin":
            print("   Exemplo: ~/Library/Application Support/.../Terminal/XXXXX/MQL5")
        else:
            print("   Exemplo: ~/.wine/drive_c/users/.../Terminal/XXXXX/MQL5")

        print()
        caminho = input("Caminho do MQL5: ").strip()

        if caminho:
            caminho_path = Path(caminho).expanduser()
            try:
                if caminho_path.exists():
                    # Verifica se é uma pasta MQL5 válida
                    try:
                        experts_exists = (caminho_path / "Experts").exists()
                        include_exists = (caminho_path / "Include").exists()
                        if experts_exists or include_exists:
                            self.mql5_path = caminho_path
                            print(f"\n✅ Usando: {self.mql5_path}\n")
                            return True
                        else:
                            print("\n⚠️  Esta pasta não parece ser uma pasta MQL5 válida.")
                            print("    Procure pela pasta que contém 'Experts' e 'Include'.\n")
                    except PermissionError:
                        # Mesmo sem permissao para verificar subpastas, tenta usar
                        self.mql5_path = caminho_path
                        print(f"\n✅ Usando: {self.mql5_path}\n")
                        return True
                else:
                    print(f"\n❌ Caminho não encontrado: {caminho_path}\n")
            except PermissionError:
                print("\n" + "="*60)
                print("  INSTALACAO MANUAL NECESSARIA")
                print("="*60)
                print("\nVoce nao tem permissao para acessar a pasta MQL5.")
                print("Siga os passos abaixo para instalar manualmente:\n")
                self._mostrar_instrucoes_manuais()
                return False

        return False

    def _mostrar_instrucoes_manuais(self):
        """Mostra instrucoes para instalacao manual"""
        print("PASSO 1: Abra o MetaTrader 5")
        print("         Va em: Arquivo > Abrir Pasta de Dados")
        print("         Isso abrira a pasta MQL5 no Explorer\n")

        print("PASSO 2: Crie as pastas (se nao existirem):")
        print("         MQL5/Experts/MWM/")
        print("         MQL5/Include/MWM/\n")

        print("PASSO 3: Copie os arquivos da pasta 'Scripts/':")
        print("         RSI_Sniper.mq5  ->  MQL5/Experts/MWM/")
        print("         RSIExport.mqh   ->  MQL5/Include/MWM/")
        print("         rsi_panel.py    ->  MQL5/Include/MWM/\n")

        print("PASSO 4: Compile no MetaEditor")
        print("         Abra o MetaEditor (F4 no MT5)")
        print("         Navegue ate: Experts > MWM > RSI_Sniper")
        print("         Pressione F7 para compilar\n")

        print("="*60)

    def criar_diretorios(self):
        """Cria as pastas necessárias"""
        print("📁 Criando estrutura de pastas...\n")

        pastas = [
            self.mql5_path / "Experts/MWM",
            self.mql5_path / "Include/MWM",
        ]

        for pasta in pastas:
            pasta.mkdir(parents=True, exist_ok=True)
            try:
                rel_path = pasta.relative_to(self.mql5_path)
                print(f"   ✓ MQL5/{rel_path}")
            except ValueError:
                print(f"   ✓ {pasta}")

        print()

    def instalar_arquivos(self):
        """Instala os arquivos do pacote automaticamente"""
        print("📦 Instalando arquivos do RSI Sniper...\n")

        # Detecta pasta raiz e pasta Scripts (onde estão os arquivos do robô)
        pasta_instalador = Path(__file__).parent.parent.resolve() / "Scripts"

        # Define mapeamento: arquivo → pasta destino
        mapeamento = {
            # O .ex5 vai pronto: e bytecode do terminal, igual em Windows,
            # macOS e Linux, entao compilar na maquina do usuario e opcional.
            # Sem ele, quem nao tem o MetaEditor no lugar esperado fica sem robo.
            'RSI_Sniper.ex5': self.mql5_path / "Experts/MWM",
            'RSI_Sniper.mq5': self.mql5_path / "Experts/MWM",
            'RSIExport.mqh': self.mql5_path / "Include/MWM",
            'rsi_panel.py': self.mql5_path / "Include/MWM",
        }

        arquivos_copiados = 0
        arquivos_faltando = []

        for nome_arquivo, destino in mapeamento.items():
            origem = pasta_instalador / nome_arquivo

            if origem.exists():
                shutil.copy2(origem, destino / nome_arquivo)
                try:
                    rel_destino = destino.relative_to(self.mql5_path)
                    print(f"   ✓ {nome_arquivo} → MQL5/{rel_destino}")
                except ValueError:
                    print(f"   ✓ {nome_arquivo} → {destino}")
                self.arquivos_instalados.append(str(destino / nome_arquivo))
                arquivos_copiados += 1
            else:
                arquivos_faltando.append(nome_arquivo)
                print(f"   ⚠️  {nome_arquivo} não encontrado na pasta do instalador")

        print()

        if arquivos_copiados == 0:
            print("❌ Nenhum arquivo encontrado para instalar!\n")
            print("📋 Certifique-se de que os seguintes arquivos estão na mesma pasta do instalador:")
            print(f"   {pasta_instalador}\n")
            for arquivo in mapeamento.keys():
                print(f"   - {arquivo}")
            print()
            return False

        if arquivos_faltando:
            print(f"⚠️  {len(arquivos_faltando)} arquivo(s) não encontrado(s):")
            for arquivo in arquivos_faltando:
                print(f"   - {arquivo}")
            print()

        print(f"✅ {arquivos_copiados} arquivo(s) instalado(s) com sucesso!\n")
        return True

    def _criar_app_bundle_macos(self, nome_app, nome_executavel, bundle_id, display_name, script_shell):
        """Cria um bundle .app real do macOS com binário shell executável."""
        pasta_instalacao = Path(__file__).resolve().parent
        app_path = pasta_instalacao / "macOS" / f"{nome_app}.app"
        contents_dir = app_path / "Contents"
        macos_dir = contents_dir / "MacOS"
        resources_dir = contents_dir / "Resources"

        if app_path.exists():
            shutil.rmtree(app_path)

        macos_dir.mkdir(parents=True, exist_ok=True)
        resources_dir.mkdir(parents=True, exist_ok=True)

        executable = macos_dir / nome_executavel
        with open(executable, 'w', encoding='utf-8') as f:
            f.write(script_shell)
        os.chmod(executable, 0o755)

        plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>{nome_executavel}</string>
    <key>CFBundleIdentifier</key>
    <string>{bundle_id}</string>
    <key>CFBundleName</key>
    <string>{display_name}</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
</dict>
</plist>
'''
        (contents_dir / "Info.plist").write_text(plist, encoding='utf-8')

        print(f"   ✓ Bundle macOS criado: {app_path}\n")
        return app_path

    def criar_atalho_desktop(self):
        """Cria o atalho do painel na Área de Trabalho e o bundle .app no macOS."""
        print("🖥️  Criando executável na Área de Trabalho...\n")

        home = Path.home()
        desktop = home / "Desktop"

        # Tenta outras localizações comuns para Desktop
        if not desktop.exists():
            desktop = home / "Área de Trabalho"
        if not desktop.exists():
            desktop = home / "Escritorio"
        if not desktop.exists():
            print("   ⚠️  Área de Trabalho não encontrada. Atalho não criado.\n")
            return None

        if self.sistema == "Darwin":
            instalador_script = '''#!/bin/bash
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")/../../../../" && pwd)"
cd "$SCRIPT_DIR" || exit 1
exec python3 install_rsi_sniper.py
'''
            painel_script = '''#!/bin/bash
set -u
WINE_BASE="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users"
PANEL_FOUND=""

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
                        break 2
                    fi
                done
            fi
        fi
    done
fi

if [ -z "$PANEL_FOUND" ]; then
    PROG_PANEL="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Include/MWM/rsi_panel.py"
    if [ -f "$PROG_PANEL" ]; then
        PANEL_DIR="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Include/MWM"
        PANEL_FOUND="1"
    fi
fi

if [ -n "$PANEL_FOUND" ]; then
    cd "$PANEL_DIR" || exit 1
    # Escolhe o Python que abre o painel de verdade, nao so o primeiro que
    # tenha tkinter. O Finder nao passa o PATH do Terminal para o aplicativo,
    # entao la so aparece /usr/bin/python3, cujo Tk 8.5.9 e o Aqua antigo:
    # ele cria a janela e nao desenha nada dentro, o painel abre em branco.
    # Por isso o Homebrew/python.org vem primeiro e o Tk 8.5 e recusado.
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
    # Aberto pelo Finder nao existe terminal: um echo aqui nao chega a ninguem,
    # o app so morre calado. Todo erro daqui pra frente vira alerta na tela.
    if [ -z "$PY" ]; then
        if [ -n "$PY_TK_VELHO" ]; then
            MSG="O Python deste Mac ($PY_TK_VELHO) traz o Tk 8.5, que abre o painel em branco.\\n\\nNo Terminal, rode:\\n    brew install python python-tk\\n\\nDepois abra o painel de novo."
        else
            MSG="Nao encontrei um Python 3 com a parte grafica (tkinter).\\n\\nNo Terminal, rode:\\n    brew install python python-tk\\n\\nDepois abra o painel de novo."
        fi
        osascript -e "display alert \\"RSI Sniper\\" message \\"$MSG\\" as critical" >/dev/null 2>&1
        exit 1
    fi
    if ! "$PY" -c "import customtkinter" >/dev/null 2>&1; then
        "$PY" -m pip install customtkinter >/dev/null 2>&1 \\
            || "$PY" -m pip install --break-system-packages customtkinter >/dev/null 2>&1
    fi
    if ! "$PY" -c "import customtkinter" >/dev/null 2>&1; then
        osascript -e "display alert \\"RSI Sniper\\" message \\"Falta a biblioteca customtkinter.\\n\\nNo Terminal, rode:\\n    $PY -m pip install customtkinter\\" as critical" >/dev/null 2>&1
        exit 1
    fi
    exec "$PY" rsi_panel.py
fi

echo "Painel RSI Sniper nao encontrado. Execute o instalador primeiro." >&2
exit 1
'''
            self._criar_app_bundle_macos(
                "Instalar_RSI_Sniper",
                "Instalar_RSI_Sniper",
                "com.mwm.rsisniper.instalador",
                "Instalar RSI Sniper",
                instalador_script,
            )
            self._criar_app_bundle_macos(
                "Abrir_Painel",
                "Abrir_Painel",
                "com.mwm.rsisniper.painel",
                "Abrir Painel",
                painel_script,
            )

            atalho = desktop / "RSI_Sniper_Painel.command"
            script_content = '''#!/bin/bash
# RSI Sniper - Painel de Controle
WINE_BASE="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users"
PANEL_FOUND=""

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
                        break 2
                    fi
                done
            fi
        fi
    done
fi

if [ -z "$PANEL_FOUND" ]; then
    PROG_PANEL="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Include/MWM/rsi_panel.py"
    if [ -f "$PROG_PANEL" ]; then
        PANEL_DIR="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Include/MWM"
        PANEL_FOUND="1"
    fi
fi

if [ -n "$PANEL_FOUND" ]; then
    cd "$PANEL_DIR"
    # Escolhe o Python que abre o painel de verdade, nao so o primeiro que
    # tenha tkinter. O Finder nao passa o PATH do Terminal para o aplicativo,
    # entao la so aparece /usr/bin/python3, cujo Tk 8.5.9 e o Aqua antigo:
    # ele cria a janela e nao desenha nada dentro, o painel abre em branco.
    # Por isso o Homebrew/python.org vem primeiro e o Tk 8.5 e recusado.
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
            echo "O Python deste Mac ($PY_TK_VELHO) traz o Tk 8.5, que abre o painel em branco."
        else
            echo "Nao encontrei um Python 3 com a parte grafica (tkinter)."
        fi
        echo "  Rode:  brew install python python-tk"
        exit 1
    fi
    "$PY" -c "import customtkinter" >/dev/null 2>&1 || "$PY" -m pip install customtkinter
    exec "$PY" rsi_panel.py
else
    echo "Painel RSI Sniper nao encontrado. Execute o instalador primeiro."
    exit 1
fi
'''
            with open(atalho, 'w') as f:
                f.write(script_content)
            os.chmod(atalho, 0o755)
            print(f"   ✓ Criado: {atalho}\n")
            return atalho

        # resto: Windows/Linux mantém o comportamento anterior

        painel_path = self.mql5_path / "Include/MWM/rsi_panel.py"
        atalho = None

        if self.sistema == "Darwin":  # macOS
            # Cria um .command com busca inteligente
            atalho = desktop / "RSI_Sniper_Painel.command"
            script_content = '''#!/bin/bash
# RSI Sniper - Painel de Controle

echo "============================================================"
echo "  RSI SNIPER - Localizando Painel..."
echo "============================================================"
echo ""

# Busca na pasta de dados do MT5 (Wine)
WINE_BASE="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users"
PANEL_FOUND=""

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
                        break 2
                    fi
                done
            fi
        fi
    done
fi

# Fallback: pasta do programa
if [ -z "$PANEL_FOUND" ]; then
    PROG_PANEL="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Include/MWM/rsi_panel.py"
    if [ -f "$PROG_PANEL" ]; then
        PANEL_DIR="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Include/MWM"
        PANEL_FOUND="1"
    fi
fi

if [ -n "$PANEL_FOUND" ]; then
    echo "Painel encontrado em:"
    echo "$PANEL_DIR"
    echo ""
    echo "Iniciando painel..."
    cd "$PANEL_DIR"
    # Procura um Python que realmente tenha a parte grafica (tkinter).
    # No macOS e comum ter varios Pythons e so alguns trazerem tkinter.
    # Escolhe o Python que abre o painel de verdade, nao so o primeiro que
    # tenha tkinter. O Finder nao passa o PATH do Terminal para o aplicativo,
    # entao la so aparece /usr/bin/python3, cujo Tk 8.5.9 e o Aqua antigo:
    # ele cria a janela e nao desenha nada dentro, o painel abre em branco.
    # Por isso o Homebrew/python.org vem primeiro e o Tk 8.5 e recusado.
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
            echo "O Python deste Mac ($PY_TK_VELHO) traz o Tk 8.5, que abre o painel em branco."
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
'''
            with open(atalho, 'w') as f:
                f.write(script_content)
            os.chmod(atalho, 0o755)
            print(f"   ✓ Criado: {atalho}\n")

        elif self.sistema == "Windows":
            # Cria um .bat com busca inteligente
            atalho = desktop / "RSI_Sniper_Painel.bat"
            script_content = '''@echo off
chcp 65001 >nul
title RSI Sniper - Painel de Controle

echo ============================================================
echo   RSI SNIPER - Localizando Painel...
echo ============================================================
echo.

REM Procura na pasta de DADOS do MT5 (AppData)
set "FOUND="
for /d %%i in ("%APPDATA%\\MetaQuotes\\Terminal\\*") do (
    if exist "%%i\\MQL5\\Include\\MWM\\rsi_panel.py" (
        set "PANEL_DIR=%%i\\MQL5\\Include\\MWM"
        set "FOUND=1"
    )
)

REM Se encontrou na pasta de dados
if defined FOUND (
    echo Painel encontrado em:
    echo %PANEL_DIR%
    echo.
    echo Iniciando painel...
    cd /d "%PANEL_DIR%"
    set "PY="
    for %%%%P in (python python3 py) do (
        if not defined PY (
            %%%%P -c "import tkinter" >nul 2>&1 && set "PY=%%%%P"
        )
    )
    if not defined PY (
        echo Python 3 nao encontrado ou sem tkinter.
        echo Instale de python.org marcando "tcl/tk and IDLE".
        pause
        exit /b 1
    )
    %%PY%% -c "import customtkinter" >nul 2>&1 || %%PY%% -m pip install customtkinter
    %%PY%% rsi_panel.py
    if errorlevel 1 (
        echo.
        echo ERRO: Falha ao executar o painel.
        echo Verifique se Python esta instalado corretamente.
        echo.
        pause
    )
    goto :end
)

REM Fallback: pasta do programa
if exist "C:\\Program Files\\MetaTrader 5\\MQL5\\Include\\MWM\\rsi_panel.py" (
    echo Painel encontrado em:
    echo C:\\Program Files\\MetaTrader 5\\MQL5\\Include\\MWM
    echo.
    echo Iniciando painel...
    cd /d "C:\\Program Files\\MetaTrader 5\\MQL5\\Include\\MWM"
    set "PY="
    for %%%%P in (python python3 py) do (
        if not defined PY (
            %%%%P -c "import tkinter" >nul 2>&1 && set "PY=%%%%P"
        )
    )
    if not defined PY (
        echo Python 3 nao encontrado ou sem tkinter.
        echo Instale de python.org marcando "tcl/tk and IDLE".
        pause
        exit /b 1
    )
    %%PY%% -c "import customtkinter" >nul 2>&1 || %%PY%% -m pip install customtkinter
    %%PY%% rsi_panel.py
    goto :end
)

REM Nao encontrou
echo.
echo ============================================================
echo   ERRO: Painel nao encontrado!
echo ============================================================
echo.
echo O arquivo rsi_panel.py nao foi encontrado.
echo.
echo Possiveis solucoes:
echo   1. Execute o instalador primeiro
echo   2. Verifique se o MetaTrader 5 esta instalado
echo   3. Verifique se Python esta instalado
echo.
pause

:end
'''
            with open(atalho, 'w') as f:
                f.write(script_content)
            print(f"   ✓ Criado: {atalho}\n")

        else:  # Linux
            # Cria um .sh com busca inteligente
            atalho = desktop / "RSI_Sniper_Painel.sh"
            script_content = '''#!/bin/bash
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
    # Escolhe o Python que abre o painel de verdade, nao so o primeiro que
    # tenha tkinter. O Finder nao passa o PATH do Terminal para o aplicativo,
    # entao la so aparece /usr/bin/python3, cujo Tk 8.5.9 e o Aqua antigo:
    # ele cria a janela e nao desenha nada dentro, o painel abre em branco.
    # Por isso o Homebrew/python.org vem primeiro e o Tk 8.5 e recusado.
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
'''
            with open(atalho, 'w') as f:
                f.write(script_content)
            os.chmod(atalho, 0o755)
            print(f"   ✓ Criado: {atalho}\n")

        return atalho

    def exibir_proximos_passos(self, atalho_desktop=None):
        """Mostra instruções de próximos passos"""
        print(f"\n{'='*60}")
        print("  ✅ INSTALAÇÃO CONCLUÍDA!")
        print(f"{'='*60}\n")

        # Destaque para o executável criado
        if atalho_desktop:
            print(f"{'='*60}")
            print("  🖥️  EXECUTÁVEL CRIADO NA ÁREA DE TRABALHO:")
            print(f"{'='*60}")
            print(f"\n   → {atalho_desktop.name}\n")
            print("   Dê duplo clique para abrir o Painel de Controle!")
            print(f"\n{'='*60}\n")

        print("📋 PRÓXIMOS PASSOS:\n")

        print("1️⃣  Abra o MetaEditor do MetaTrader 5")
        print("   (Pressione F4 dentro do MT5)\n")

        print("2️⃣  Compile o Expert Advisor:")
        print("   • Navegue até: Experts → MWM → RSI_Sniper.mq5")
        print("   • Pressione F7 para compilar\n")

        print("3️⃣  Execute o painel de controle:")
        if atalho_desktop:
            print(f"   • Dê duplo clique em: {atalho_desktop.name}")
        else:
            print("   • Use o atalho na Área de Trabalho")
        print("   • (Localizado na sua Área de Trabalho)\n")

        print("4️⃣  No MetaTrader 5:")
        print("   • Navegador → Expert Advisors → MWM → RSI_Sniper")
        print("   • Arraste para o gráfico do ativo desejado")
        print("   • Configure os parâmetros e clique OK\n")

        print(f"{'='*60}")
        print("  📁 ARQUIVOS INSTALADOS:")
        print(f"{'='*60}\n")

        for arquivo in self.arquivos_instalados:
            print(f"   ✓ {arquivo}")

        if atalho_desktop:
            print(f"   ✓ {atalho_desktop} (Área de Trabalho)")

        print(f"\n{'='*60}\n")

    # ==================================================================
    # DEPENDENCIAS DO PAINEL
    # ==================================================================

    def python_do_painel(self):
        """
        Descobre com qual Python o painel vai rodar.

        Prefere um que já tenha o tkinter funcionando — no macOS é comum ter
        vários Pythons instalados e só alguns trazerem a parte gráfica.
        Retorna (caminho, tem_tkinter).
        """
        candidatos = [sys.executable]
        for nome in ("python3", "python"):
            achado = shutil.which(nome)
            if achado and achado not in candidatos:
                candidatos.append(achado)
        if self.sistema == "Darwin":
            for extra in ("/usr/bin/python3", "/opt/homebrew/bin/python3"):
                if os.path.exists(extra) and extra not in candidatos:
                    candidatos.append(extra)

        primeiro = None
        for caminho in candidatos:
            if not caminho:
                continue
            if primeiro is None:
                primeiro = caminho
            try:
                r = subprocess.run([caminho, "-c", "import tkinter"],
                                   capture_output=True, timeout=20)
                if r.returncode == 0:
                    return caminho, True
            except Exception:
                continue
        return primeiro or sys.executable, False

    def preparar_painel(self):
        """
        Garante que o painel tem tudo para abrir: tkinter e customtkinter.

        O tkinter não dá para instalar por pip — depende do sistema —, então
        quando falta o instalador diz o comando exato para resolver.
        """
        print("\n📦 Verificando o que o painel precisa...\n")
        py, tem_tk = self.python_do_painel()
        self.python_painel = py
        print(f"   Python usado pelo painel: {py}")

        if tem_tk:
            print("   ✓ tkinter disponível")
        else:
            print("   ✗ tkinter NÃO encontrado — sem ele o painel não abre")
            if self.sistema == "Darwin":
                versao = f"{sys.version_info.major}.{sys.version_info.minor}"
                print(f"      Resolva com:  brew install python-tk@{versao}")
            elif self.sistema == "Linux":
                print("      Resolva com:  sudo apt install python3-tk")
            else:
                print("      Reinstale o Python marcando a opção 'tcl/tk and IDLE'")

        try:
            r = subprocess.run([py, "-c", "import customtkinter"],
                               capture_output=True, timeout=25)
            if r.returncode == 0:
                print("   ✓ customtkinter já instalado")
                return tem_tk
        except Exception:
            pass

        print("   → instalando customtkinter...")
        for args in (["-m", "pip", "install", "customtkinter"],
                     ["-m", "pip", "install", "--user", "customtkinter"],
                     ["-m", "pip", "install", "--break-system-packages", "customtkinter"]):
            try:
                r = subprocess.run([py] + args, capture_output=True, timeout=300)
                if r.returncode == 0:
                    print("   ✓ customtkinter instalado")
                    return tem_tk
            except Exception:
                continue

        print("   ✗ não consegui instalar automaticamente")
        print(f"      Rode você mesmo:  {py} -m pip install customtkinter")
        return False

    # ==================================================================
    # COMPILACAO DO ROBO
    # ==================================================================

    def compilar_ea(self):
        """
        Compila o RSI_Sniper.mq5, gerando o .ex5 que o MetaTrader executa.

        Sem isto o robô aparece na lista mas não roda — e compilar à mão no
        MetaEditor é justamente onde o iniciante trava.
        """
        print("\n⚙️  Compilando o robô...\n")
        alvo = self.mql5_path / "Experts/MWM/RSI_Sniper.mq5"
        if not alvo.exists():
            print("   ✗ RSI_Sniper.mq5 não encontrado; pule para o MetaEditor (F7)")
            return False

        editores, prefixo = [], None
        if self.sistema == "Windows":
            # Cada corretora distribui o terminal com o seu nome de pasta, entao
            # procurar so em "MetaTrader 5" deixa de fora a maioria das instalacoes
            # reais. Sobe pelos pais da pasta de dados (pega instalacao portatil)
            # e depois varre os Program Files atras de qualquer pasta com o editor.
            candidatos = list(self.mql5_path.parents)
            for raiz in (r"C:\Program Files", r"C:\Program Files (x86)",
                         os.path.expandvars(r"%LOCALAPPDATA%\Programs")):
                try:
                    if os.path.isdir(raiz):
                        candidatos += [Path(raiz) / d for d in os.listdir(raiz)]
                except (PermissionError, OSError):
                    pass
            vistos = set()
            for base in candidatos:
                base = str(base)
                if base in vistos:
                    continue
                vistos.add(base)
                for exe in ("metaeditor64.exe", "metaeditor.exe"):
                    caminho = os.path.join(base, exe)
                    if os.path.exists(caminho):
                        editores.append((caminho, base))
        else:
            wine = shutil.which("wine")
            mac_wine = "/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine"
            if self.sistema == "Darwin" and os.path.exists(mac_wine):
                wine = mac_wine
                prefixo = str(Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5")
            if wine:
                base = None
                for p in self.mql5_path.parents:
                    if (p / "metaeditor64.exe").exists():
                        base = str(p); break
                if base:
                    editores.append((wine, base))

        if not editores:
            print("   ⚠️  MetaEditor não localizado, então não recompilei aqui.")
            print("      O robô já vai compilado no pacote, então dá para usar assim mesmo.")
            print("      Só precisa do F7 se você alterar o RSI_Sniper.mq5.")
            return False

        for editor, base in editores:
            try:
                env = dict(os.environ)
                if prefixo:
                    env["WINEPREFIX"] = prefixo
                    env["DYLD_FALLBACK_LIBRARY_PATH"] = (
                        "/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/lib/external:"
                        "/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/lib:/usr/lib")
                if editor.endswith("wine"):
                    cmd = [editor, "metaeditor64.exe", "/portable",
                           "/compile:MQL5\\Experts\\MWM\\RSI_Sniper.mq5", "/log"]
                else:
                    cmd = [editor, "/portable",
                           "/compile:MQL5\\Experts\\MWM\\RSI_Sniper.mq5", "/log"]
                subprocess.run(cmd, cwd=base, capture_output=True, timeout=180, env=env)
            except Exception:
                continue

            if (self.mql5_path / "Experts/MWM/RSI_Sniper.ex5").exists():
                print("   ✓ robô compilado — já dá para anexar ao gráfico")
                return True

        print("   ⚠️  não consegui compilar aqui; abra o MetaEditor e aperte F7")
        return False

    def executar(self):
        """Executa o instalador"""
        try:
            if not self.detectar_mt5():
                return False

            self.criar_diretorios()

            if not self.instalar_arquivos():
                print("⚠️  Instalação incompleta. Verifique os arquivos faltantes.\n")
                return False

            self.compilar_ea()
            self.preparar_painel()

            atalho = self.criar_atalho_desktop()
            self.exibir_proximos_passos(atalho)
            return True

        except KeyboardInterrupt:
            print("\n\n⚠️  Instalação cancelada pelo usuário.\n")
            return False
        except Exception as e:
            print(f"\n\n❌ Erro durante instalação: {e}\n")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Função principal"""
    instalador = RSISniperInstaller()
    sucesso = instalador.executar()

    # Pausa para o usuário ler (útil quando executado via duplo-clique)
    input("\nPressione ENTER para fechar...")
    sys.exit(0 if sucesso else 1)

if __name__ == "__main__":
    main()
