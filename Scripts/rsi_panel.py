"""
+------------------------------------------------------------------+
|                    RSI SNIPER PRO - Painel                       |
|                                                                  |
| Painel de controle para o robô RSI Sniper (MetaTrader 5)         |
| - Monitora posições, lucro, RSI e filtros em tempo real          |
| - Envia comandos: pausar, fechar posições, salvar configs        |
| - Comunicação via arquivos JSON na pasta Common/Files            |
|                                                                  |
| Compatível com: Windows, macOS (Wine) e Linux (Wine)             |
+------------------------------------------------------------------+
"""

# ═══════════════════════════════════════════════════════════════
# VERIFICAÇÃO E INSTALAÇÃO AUTOMÁTICA DE DEPENDÊNCIAS
# ═══════════════════════════════════════════════════════════════
import subprocess
import sys

def instalar_dependencias():
    """Verifica e instala dependências necessárias automaticamente."""
    dependencias = {
        'customtkinter': 'customtkinter',
    }

    for modulo, pacote in dependencias.items():
        try:
            __import__(modulo)
        except ImportError:
            print(f"Instalando {pacote}...")
            try:
                subprocess.check_call([
                    sys.executable, '-m', 'pip', 'install', pacote, '--quiet'
                ])
                print(f"✓ {pacote} instalado com sucesso!")
            except subprocess.CalledProcessError:
                print(f"✗ Erro ao instalar {pacote}.")
                print(f"  Execute manualmente: pip install {pacote}")
                input("Pressione ENTER para sair...")
                sys.exit(1)

# Executa verificação antes de importar
instalar_dependencias()

import customtkinter as ctk
from tkinter import messagebox, TclError
import json
import re
import os
from datetime import datetime
import time
from pathlib import Path
import platform

# Tema escuro é padrão para trading (menos cansaço visual)
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def ligar_evento(widget, evento, funcao, todos=False):
    """
    Liga um evento tolerando o que a versão do Tk não conhece.

    <TouchpadScroll> só existe a partir do Tk 9, que é o que vem no Python
    do macOS. O Python do Windows ainda traz Tk 8.6, onde só tentar ligar
    esse evento levanta TclError e derruba o painel na criação do primeiro
    card. Lá o <MouseWheel> continua sendo disparado normalmente, então
    ignorar o evento inexistente não custa rolagem nenhuma.

    Devolve True se o evento existe nesta versão do Tk.
    """
    try:
        ligar = widget.bind_all if todos else widget.bind
        ligar(evento, funcao, add=True)
        return True
    except TclError:
        return False


class RSIPanelModern(ctk.CTk):
    """
    Painel principal do RSI Sniper.

    O painel lê dados do EA via arquivo JSON (rsi_data_LIVE.json ou rsi_data_BACKTEST.json)
    e envia comandos via arquivo TXT (rsi_commands_*.txt).

    O EA exporta os dados a cada tick, e o painel atualiza a cada 250ms.
    """
    def __init__(self):
        super().__init__()

        self.sistema = platform.system()

        # ═══════════════════════════════════════════════════════════════
        # PALETA DE CORES - Estilo Trading Dashboard
        # Mantém consistência visual em todo o painel
        # ═══════════════════════════════════════════════════════════════
        self.colors = {
            # Fundos (escuros para reduzir cansaço visual em longas sessões)
            'bg_primary': '#0a0e14',      # Fundo principal (preto profundo)
            'bg_secondary': '#111820',    # Card background
            'bg_tertiary': '#1a2332',     # Input/elevated
            'bg_hover': '#232d3f',         # Hover states

            # Accent Colors
            'accent_cyan': '#00d4ff',      # Primary accent
            'accent_green': '#00ff88',     # Profit/Success
            'accent_red': '#ff3366',       # Loss/Error
            'accent_yellow': '#ffcc00',    # Warning
            'accent_purple': '#a855f7',    # Secondary accent
            'accent_blue': '#3b82f6',      # Info

            # Text
            'text_primary': '#ffffff',
            'text_secondary': '#94a3b8',
            'text_muted': '#64748b',

            # Borders & Effects
            'border': '#1e293b',
            'border_glow': '#00d4ff',
            'gradient_start': '#0a0e14',
            'gradient_end': '#111820',
        }

        # Window setup - tamanho compacto
        self.title(f"RSI SNIPER PRO")
        # A altura é ditada pela coluna de Monitoramento, que é a mais alta:
        # Agressão, Volume Profile, Tendência, Volatilidade e Status, com os
        # separadores entre eles. Abrir menor que isso corta o Status embaixo.
        # Medida pela coluna de Monitoramento, que é a mais alta. Encolheu
        # quando o Status saiu daqui e subiu para o Monitor.
        # Medido com RSI_MEDIR_ALTURA=1: Monitor 611px, Configuracoes 630px,
        # Monitoramento 302px com tudo desligado e 416px so com a tendencia,
        # que e a configuracao usada. Cada filtro ligado adiciona o proprio
        # bloco; com os quatro abertos passa de 1100px e nao cabe em 1080.
        ALTURA_CONTEUDO = 800   # so o palpite inicial; _ajustar_altura_janela corrige
        LARGURA_CONTEUDO = 1150

        altura = min(ALTURA_CONTEUDO, self.winfo_screenheight() - 80)
        largura = min(LARGURA_CONTEUDO, self.winfo_screenwidth() - 40)

        self.geometry(f"{largura}x{altura}")

        # Medicao de altura para conferir se tudo cabe sem rolagem:
        #   RSI_MEDIR_ALTURA=1 python3 rsi_panel.py
        if os.environ.get("RSI_MEDIR_ALTURA"):
            def _medir():
                import itertools
                for estado in (0, 1, 2):
                    # 0 = todos fechados | 1 = so tendencia (config campea) | 2 = todos abertos
                    self.agressao_var.set(estado == 2)
                    self.volume_profile_var.set(estado == 2)
                    self.tendencia_var.set(estado >= 1)
                    self.atr_var.set(estado == 2)
                    self._refletir_expansao()
                    self.update_idletasks()
                    rotulo = {0: "nenhum filtro", 1: "so tendencia", 2: "os quatro"}[estado]
                    saida = []
                    for f in self.winfo_children():
                        for n in f.winfo_children():
                            if n.winfo_class() != "Frame":
                                continue
                            info = n.grid_info()
                            if not info:
                                continue
                            saida.append(f"col{info.get('column')}={n.winfo_reqheight()}px")
                    print(f"{rotulo:<15} " + "  ".join(saida) + f"   (janela {altura}px)")
                for filho in self.winfo_children():
                    for neto in filho.winfo_children():
                        if neto.winfo_class() == "Frame" and neto.winfo_reqheight() > 200:
                            print(f"coluna: precisa {neto.winfo_reqheight()}px | janela tem {altura}px")
                self.after(200, self.destroy)
            self.after(2500, _medir)
        self.configure(fg_color=self.colors['bg_primary'])
        self.minsize(min(1050, largura), 600)
        self.MARGEM_JANELA = 24   # respiro entre a coluna mais alta e a borda

        # Detecta caminho do MetaTrader
        self.common_path = self._detectar_caminho()
        self.modo_atual = self._detectar_modo()
        self._atualizar_arquivos()

        print("=" * 60)
        print(f"  RSI SNIPER PRO - Trading Dashboard ({self.sistema})")
        print("=" * 60)
        print(f"  Modo: {self.modo_atual}")
        print(f"  Dados: {self.data_file}")
        print("=" * 60)

        os.makedirs(self.common_path, exist_ok=True)

        # Variáveis de controle
        self.trailing_var = ctk.BooleanVar(value=True)
        self.agressao_var = ctk.BooleanVar(value=False)
        self.volume_profile_var = ctk.BooleanVar(value=False)
        self.tendencia_var = ctk.BooleanVar(value=False)
        self.atr_var = ctk.BooleanVar(value=False)
        self.ultimo_timestamp = None
        self.conexao_ativa = False
        self.checkboxes_sincronizados = False
        self.entries_param = {}
        self.blocos_monitor = {}
        self.menus_param = {}
        self.info_labels = {}
        self.entries = {}

        # Controle de timeout de conexão (15 segundos sem dados = desconectado)
        # Aumentado para 15s porque no backtest pode haver gaps sem ticks
        self.ultima_atualizacao_real = None  # Momento real que recebeu dados
        self.timeout_conexao = 15   # Segundos sem dado = desconectado (ao vivo)
        self.timeout_backtest = 20  # Sem dado por este tempo em teste = terminou

        self._criar_interface()
        self._refletir_trailing()   # esconde a distância se o trailing vier desligado
        self._limitar_a_numeros()   # campos de risco só aceitam número
        # Depois de tudo montado, a janela assume o tamanho do conteudo real
        self.after(120, self._ajustar_altura_janela)

        self._atualizar_dados()

    def _detectar_modo(self):
        """
        Detecta automaticamente se está rodando BACKTEST ou LIVE.
        Usa o arquivo modificado mais recentemente como referência.
        Isso permite alternar entre modos sem reiniciar o painel.
        """
        backtest_file = os.path.join(self.common_path, "rsi_data_BACKTEST.json")
        live_file = os.path.join(self.common_path, "rsi_data_LIVE.json")
        legacy_file = os.path.join(self.common_path, "rsi_data.json")

        files = {}
        for nome, path in [("BACKTEST", backtest_file), ("LIVE", live_file), ("LEGACY", legacy_file)]:
            if os.path.exists(path):
                files[nome] = os.path.getmtime(path)

        if not files:
            return "BACKTEST"
        return max(files, key=files.get)

    def _atualizar_arquivos(self):
        if self.modo_atual == "LEGACY":
            self.data_file = os.path.join(self.common_path, "rsi_data.json")
            self.command_file = os.path.join(self.common_path, "rsi_commands.txt")
        else:
            sufixo = f"_{self.modo_atual}"
            self.data_file = os.path.join(self.common_path, f"rsi_data{sufixo}.json")
            self.command_file = os.path.join(self.common_path, f"rsi_commands{sufixo}.txt")

    @staticmethod
    def _frescor_dados(common_path):
        """
        Retorna o mtime do JSON mais recente do EA dentro de uma pasta Common/Files.

        Serve de criterio de desempate quando existe mais de uma pasta candidata:
        a que o EA esta escrevendo tem dado fresco, as outras retornam 0.
        """
        melhor = 0.0
        for nome in ("rsi_data_LIVE.json", "rsi_data_BACKTEST.json", "rsi_data.json"):
            try:
                melhor = max(melhor, os.path.getmtime(os.path.join(str(common_path), nome)))
            except OSError:
                continue  # arquivo nao existe nessa pasta
        return melhor

    def _detectar_caminho(self):
        """
        Encontra a pasta Common/Files do MetaTrader automaticamente.

        - macOS: usa Wine prefix em ~/Library/Application Support/...
        - Windows: usa %APPDATA%/MetaQuotes/...
        - Linux: usa ~/.wine/drive_c/...

        Tenta múltiplos caminhos possíveis e retorna o primeiro que existir.
        """
        sistema = platform.system()
        home = Path.home()
        usuario_sistema = os.getenv("USER", "user")

        if sistema == "Darwin":
            wine_prefix = home / "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c"
            caminhos_possiveis = []

            # O Wine costuma criar mais de um perfil em drive_c/users (ex: "user"
            # alem do usuario real), e so um deles recebe os JSON do EA. Ordenar
            # por "quem tem dado mais recente" evita apontar para a pasta vazia.
            users_dir = wine_prefix / "users"
            if users_dir.exists():
                candidatos = []
                for user_folder in sorted(users_dir.iterdir()):
                    if not user_folder.is_dir():
                        continue
                    common_path = user_folder / "AppData/Roaming/MetaQuotes/Terminal/Common/Files"
                    if not common_path.exists():
                        continue
                    candidatos.append((self._frescor_dados(common_path), common_path))

                # Mais recente primeiro; pastas sem dado nenhum ficam por ultimo.
                candidatos.sort(key=lambda item: item[0], reverse=True)
                caminhos_possiveis.extend(caminho for _, caminho in candidatos)

            caminhos_possiveis.extend([
                wine_prefix / "users" / usuario_sistema / "AppData/Roaming/MetaQuotes/Terminal/Common/Files",
                wine_prefix / "users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files",
            ])
        elif sistema == "Windows":
            caminhos_possiveis = [
                Path(os.environ.get("APPDATA", "")) / "MetaQuotes/Terminal/Common/Files",
            ]
        else:
            caminhos_possiveis = [
                home / ".wine/drive_c/users" / usuario_sistema / "AppData/Roaming/MetaQuotes/Terminal/Common/Files",
            ]

        for caminho in caminhos_possiveis:
            if caminho.exists():
                return str(caminho)

        return str(caminhos_possiveis[0] if caminhos_possiveis else home / "MetaQuotes/Terminal/Common/Files")

    # ═══════════════════════════════════════════════════════════════
    # INTERFACE - Modern Trading Dashboard
    # ═══════════════════════════════════════════════════════════════

    def _criar_interface(self):
        # Header
        self._criar_header()

        # Main container
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        # Grid layout - 3 colunas
        main_container.grid_columnconfigure(0, weight=1, uniform="cols")
        main_container.grid_columnconfigure(1, weight=1, uniform="cols")
        main_container.grid_columnconfigure(2, weight=1, uniform="cols")
        main_container.grid_rowconfigure(0, weight=1)

        # Colunas
        self._criar_coluna_monitor(main_container)
        self._criar_coluna_monitoramento(main_container)
        self._criar_coluna_configuracoes(main_container)


    def _criar_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent", height=60)
        header.pack(fill="x", padx=20, pady=(15, 8))
        header.pack_propagate(False)

        # Logo e título
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", fill="y")

        # Logo icon (simulated with Unicode)
        logo_label = ctk.CTkLabel(
            title_frame,
            text="🎯",
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color=self.colors['accent_cyan']
        )
        logo_label.pack(side="left", padx=(0, 12))

        title_text_frame = ctk.CTkFrame(title_frame, fg_color="transparent")
        title_text_frame.pack(side="left")

        ctk.CTkLabel(
            title_text_frame,
            text="RSI SNIPER",
            font=ctk.CTkFont(family="Helvetica", size=28, weight="bold"),
            text_color=self.colors['text_primary']
        ).pack(anchor="w")

        # Status de conexão (direita)
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.pack(side="right", fill="y")

        self.status_indicator = ctk.CTkFrame(
            status_frame,
            width=12, height=12,
            corner_radius=6,
            fg_color=self.colors['accent_yellow']
        )
        self.status_indicator.pack(side="right", pady=20)

        self.lbl_conexao = ctk.CTkLabel(
            status_frame,
            text="Conectando...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors['accent_yellow']
        )
        self.lbl_conexao.pack(side="right", padx=(0, 10), pady=20)

        # Modo badge
        self.modo_badge = ctk.CTkLabel(
            status_frame,
            text=f"● {self.modo_atual}",
            font=ctk.CTkFont(size=11),
            text_color=self.colors['accent_purple'],
            fg_color=self.colors['bg_tertiary'],
            corner_radius=12,
            padx=12, pady=4
        )
        self.modo_badge.pack(side="right", padx=(0, 15), pady=18)

    def _criar_card(self, parent, titulo, row=0, col=0, icon="", rolavel=False):
        """Cria um card moderno compacto"""
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors['bg_secondary'],
            corner_radius=12,
            border_width=1,
            border_color=self.colors['border']
        )
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

        # Header do card
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(12, 0))

        title_with_icon = f"{icon} {titulo}" if icon else titulo
        ctk.CTkLabel(
            header_frame,
            text=title_with_icon,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.colors['accent_cyan']
        ).pack(side="left")

        # Separator line
        sep_frame = ctk.CTkFrame(card, fg_color="transparent", height=2)
        sep_frame.pack(fill="x", padx=15, pady=(10, 0))

        sep = ctk.CTkFrame(sep_frame, height=1, fg_color=self.colors['border'])
        sep.pack(fill="x")

        # Content area
        # Card rolavel: quando a janela bate no limite da tela, a rolagem
        # acontece aqui dentro, e nao na janela inteira.
        if rolavel:
            content = ctk.CTkScrollableFrame(
                card, fg_color="transparent",
                scrollbar_button_color=self.colors['bg_hover'],
                scrollbar_button_hover_color=self.colors['border']
            )
            content.pack(fill="both", expand=True, padx=8, pady=12)
            self._preparar_card_rolavel(content)
        else:
            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="both", expand=True, padx=15, pady=12)

        return content, card

    def _criar_info_row(self, parent, label, key, is_value_large=False):
        """Cria uma linha de informação estilizada"""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=8)

        ctk.CTkLabel(
            row,
            text=label,
            font=ctk.CTkFont(size=13),
            text_color=self.colors['text_secondary'],
            anchor="w",
            width=120
        ).pack(side="left")

        font_size = 16 if is_value_large else 14   # mesma escala nas tres colunas
        lbl = ctk.CTkLabel(
            row,
            text="--",
            font=ctk.CTkFont(size=font_size, weight="bold"),
            text_color=self.colors['accent_cyan'],
            anchor="e"
        )
        lbl.pack(side="right")
        self.info_labels[key] = lbl

        return row

    def _criar_coluna_monitor(self, parent):
        col_frame = ctk.CTkFrame(parent, fg_color="transparent")
        col_frame.grid(row=0, column=0, sticky="nsew")
        col_frame.grid_rowconfigure(0, weight=1)
        col_frame.grid_rowconfigure(1, weight=0)
        col_frame.grid_columnconfigure(0, weight=1)

        # Card Monitor
        content, card = self._criar_card(col_frame, "MONITOR", 0, 0, "📊")

        # Status badge grande
        status_container = ctk.CTkFrame(content, fg_color="transparent")
        status_container.pack(fill="x", pady=(0, 12))

        self.status_badge = ctk.CTkLabel(
            status_container,
            text="● DESCONECTADO",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors['accent_yellow'],
            fg_color=self.colors['bg_tertiary'],
            corner_radius=8,
            padx=16, pady=8
        )
        self.status_badge.pack(side="left")

        # O que o robô está pensando, em português. É a única linha do painel
        # que se entende sem saber nada de trading, então vem antes dos números.
        # Na mesma linha do badge: o estado do robô e o que ele está vendo,
        # lado a lado. O número do RSI sai daqui — ele já tem linha própria
        # logo abaixo, e sem ele o texto cabe sem quebrar.
        self.lbl_sinal_status = ctk.CTkLabel(
            status_container,
            text="Aguardando sinal",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors['accent_yellow'],
            anchor="e"
        )
        # À direita, como todo valor do painel: o badge é o rótulo da linha.
        self.lbl_sinal_status.pack(side="right")

        # Informações principais
        self._criar_info_row(content, "Data:", "data_pregao")
        self._criar_info_row(content, "Ativo:", "ativo")
        self._criar_info_row(content, "Posições:", "posicoes")
        self._criar_info_row(content, "RSI:", "rsi")

        # Separator
        ctk.CTkFrame(content, height=1, fg_color=self.colors['border']).pack(fill="x", pady=10)

        # Valores financeiros (destaque)
        finance_frame = ctk.CTkFrame(content, fg_color=self.colors['bg_tertiary'], corner_radius=10)
        finance_frame.pack(fill="x", pady=3)

        finance_inner = ctk.CTkFrame(finance_frame, fg_color="transparent")
        finance_inner.pack(fill="x", padx=12, pady=10)

        # Lucro do Dia - Grande
        ctk.CTkLabel(
            finance_inner,
            text="LUCRO DO DIA",
            font=ctk.CTkFont(size=10),
            text_color=self.colors['text_muted']
        ).pack(anchor="w")

        self.info_labels['lucro_dia'] = ctk.CTkLabel(
            finance_inner,
            text="R$ 0.00",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=self.colors['accent_green']
        )
        self.info_labels['lucro_dia'].pack(anchor="w", pady=(2, 10))

        # Saldo e Lucro Aberto
        sub_frame = ctk.CTkFrame(finance_inner, fg_color="transparent")
        sub_frame.pack(fill="x")

        # Saldo
        saldo_col = ctk.CTkFrame(sub_frame, fg_color="transparent")
        saldo_col.pack(side="left", expand=True, fill="x")

        ctk.CTkLabel(
            saldo_col,
            text="Saldo",
            font=ctk.CTkFont(size=10),
            text_color=self.colors['text_muted']
        ).pack(anchor="w")

        self.info_labels['saldo'] = ctk.CTkLabel(
            saldo_col,
            text="R$ 0.00",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.colors['text_primary']
        )
        self.info_labels['saldo'].pack(anchor="w")

        # Lucro Aberto
        lucro_col = ctk.CTkFrame(sub_frame, fg_color="transparent")
        lucro_col.pack(side="right", expand=True, fill="x")

        ctk.CTkLabel(
            lucro_col,
            text="Lucro Aberto",
            font=ctk.CTkFont(size=10),
            text_color=self.colors['text_muted']
        ).pack(anchor="e")

        self.info_labels['lucro_aberto'] = ctk.CTkLabel(
            lucro_col,
            text="R$ 0.00",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.colors['accent_green']
        )
        self.info_labels['lucro_aberto'].pack(anchor="e")

        # Lucro Total (apenas em BACKTEST) - acumula todo o backtest
        self.lucro_total_frame = ctk.CTkFrame(finance_frame, fg_color="transparent")
        self.lucro_total_frame.pack(fill="x", padx=12, pady=(5, 10))

        ctk.CTkLabel(
            self.lucro_total_frame,
            text="LUCRO TOTAL (BACKTEST)",
            font=ctk.CTkFont(size=10),
            text_color=self.colors['accent_purple']
        ).pack(side="left")

        self.info_labels['lucro_total'] = ctk.CTkLabel(
            self.lucro_total_frame,
            text="R$ 0.00",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors['accent_cyan']
        )
        self.info_labels['lucro_total'].pack(side="right")

        # Oculta frame de lucro total se não for BACKTEST
        if self.modo_atual != "BACKTEST":
            self.lucro_total_frame.pack_forget()

        # Botões de ação
        btn_card = ctk.CTkFrame(col_frame, fg_color=self.colors['bg_secondary'], corner_radius=12)
        btn_card.grid(row=1, column=0, sticky="ew", padx=6, pady=6)

        btn_frame = ctk.CTkFrame(btn_card, fg_color="transparent")
        btn_frame.pack(pady=12, padx=15, fill="x")

        self.btn_pausar = ctk.CTkButton(
            btn_frame,
            text="⏸ PAUSAR",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.colors['accent_yellow'],
            hover_color="#cc9900",
            text_color="#000000",
            corner_radius=8,
            height=38,
            command=self._pausar_retomar
        )
        self.btn_pausar.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.btn_fechar = ctk.CTkButton(
            btn_frame,
            text="✕ FECHAR TUDO",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.colors['accent_red'],
            hover_color="#cc2952",
            text_color="#ffffff",
            corner_radius=8,
            height=38,
            command=self._fechar_tudo
        )
        self.btn_fechar.pack(side="right", expand=True, fill="x", padx=(6, 0))

        # Botão PARAR EA - largura total (abaixo dos outros)
        self.btn_parar = ctk.CTkButton(
            btn_card,
            text="⏹ PARAR EA",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            text_color="#ffffff",
            corner_radius=8,
            height=42,
            command=self._parar_ea
        )
        self.btn_parar.pack(fill="x", padx=15, pady=(0, 12))

    def _criar_coluna_monitoramento(self, parent):
        col_frame = ctk.CTkFrame(parent, fg_color="transparent")
        col_frame.grid(row=0, column=1, sticky="nsew")
        col_frame.grid_rowconfigure(0, weight=1)
        col_frame.grid_columnconfigure(0, weight=1)

        content, card = self._criar_card(col_frame, "MONITORAMENTO", 0, 0, "📈", rolavel=True)

        # ═══ AGRESSÃO ═══
        agressao_header = ctk.CTkFrame(content, fg_color="transparent")
        agressao_header.pack(fill="x", pady=(0, 10))

        self.lbl_agressao_status = ctk.CTkLabel(
            agressao_header,
            text="DESATIVADO",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=self.colors['accent_red']
        )
        self.lbl_agressao_status.pack(side="right")

        # Corpo do bloco: some quando o filtro esta desligado, porque leitura
        # e parametro de filtro inativo nao dizem nada.
        self.chk_agressao = ctk.CTkCheckBox(
            agressao_header,
            text="AGRESSÃO",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors['accent_green'],
            fg_color=self.colors['accent_green'],
            hover_color="#00cc77",
            variable=self.agressao_var,
            checkbox_width=20,
            checkbox_height=20,
            command=self._ao_marcar_filtro
        )
        self.chk_agressao.pack(side="left")

        corpo_agressao = ctk.CTkFrame(content, fg_color="transparent")
        corpo_agressao.pack(fill="x")
        self.blocos_monitor["agressao"] = (corpo_agressao, agressao_header)

        # Campos Agressão
        for label, key in [("Compra:", "agressao_compra"), ("Venda:", "agressao_venda"),
                           ("Volume:", "agressao_vol"), ("Direção:", "agressao_direcao")]:
            row = ctk.CTkFrame(corpo_agressao, fg_color="transparent")
            row.pack(fill="x", pady=5)

            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13),
                        text_color=self.colors['text_muted'], width=90, anchor="w").pack(side="left")

            lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(size=14, weight="bold"),
                              text_color=self.colors['text_secondary'], anchor="e")
            lbl.pack(side="right")
            self.info_labels[key] = lbl

        # Separator
        
        for label, key, default in [('Janela (seg):', 'agr_janela', '1'), ('Volume mín.:', 'agr_volmin', '500'), ('Confirmação:', 'agr_pctmin', '0.70')]:
            row = ctk.CTkFrame(corpo_agressao, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12),
                        text_color=self.colors['text_muted'], width=95, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, font=ctk.CTkFont(size=12),
                             fg_color=self.colors['bg_tertiary'],
                             border_color=self.colors['border'],
                             text_color=self.colors['text_primary'],
                             corner_radius=8, height=30, width=95)
            e.pack(side="right")
            e.insert(0, default)
            self.entries_param[key] = e


        ctk.CTkFrame(content, height=1, fg_color=self.colors['border']).pack(fill="x", pady=10)

        # ═══ VOLUME PROFILE ═══
        vp_header = ctk.CTkFrame(content, fg_color="transparent")
        vp_header.pack(fill="x", pady=(0, 10))

        self.lbl_vp_status = ctk.CTkLabel(
            vp_header,
            text="DESATIVADO",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=self.colors['accent_red']
        )
        self.lbl_vp_status.pack(side="right")

        # Corpo do bloco: some quando o filtro esta desligado, porque leitura
        # e parametro de filtro inativo nao dizem nada.
        self.chk_volume_profile = ctk.CTkCheckBox(
            vp_header,
            text="VOLUME PROFILE",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors['accent_purple'],
            fg_color=self.colors['accent_purple'],
            hover_color=self.colors['accent_blue'],
            variable=self.volume_profile_var,
            checkbox_width=20,
            checkbox_height=20,
            command=self._ao_marcar_filtro
        )
        self.chk_volume_profile.pack(side="left")

        corpo_vp = ctk.CTkFrame(content, fg_color="transparent")
        corpo_vp.pack(fill="x")
        self.blocos_monitor["vp"] = (corpo_vp, vp_header)

        # Campos Volume Profile
        for label, key in [("POC:", "vp_poc"), ("VAH:", "vp_vah"),
                           ("VAL:", "vp_val"), ("Zona:", "vp_zona")]:
            row = ctk.CTkFrame(corpo_vp, fg_color="transparent")
            row.pack(fill="x", pady=5)

            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13),
                        text_color=self.colors['text_muted'], width=90, anchor="w").pack(side="left")

            lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(size=14, weight="bold"),
                              text_color=self.colors['text_secondary'], anchor="e")
            lbl.pack(side="right")
            self.info_labels[key] = lbl

        # Separator
        
        for label, key, default in [('Candles:', 'vp_barras', '60'), ('Agrupamento:', 'vp_passo', '5'), ('Zona do POC:', 'vp_margem', '10')]:
            row = ctk.CTkFrame(corpo_vp, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12),
                        text_color=self.colors['text_muted'], width=95, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, font=ctk.CTkFont(size=12),
                             fg_color=self.colors['bg_tertiary'],
                             border_color=self.colors['border'],
                             text_color=self.colors['text_primary'],
                             corner_radius=8, height=30, width=95)
            e.pack(side="right")
            e.insert(0, default)
            self.entries_param[key] = e

        ctk.CTkFrame(content, height=1, fg_color=self.colors['border']).pack(fill="x", pady=10)

        # ═══ TENDÊNCIA ═══
        tend_header = ctk.CTkFrame(content, fg_color="transparent")
        tend_header.pack(fill="x", pady=(0, 10))

        self.lbl_tend_status = ctk.CTkLabel(
            tend_header,
            text="DESATIVADO",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=self.colors['accent_red']
        )
        self.lbl_tend_status.pack(side="right")

        # Corpo do bloco: some quando o filtro esta desligado, porque leitura
        # e parametro de filtro inativo nao dizem nada.
        self.chk_tendencia = ctk.CTkCheckBox(
            tend_header,
            text="TENDÊNCIA",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors['accent_yellow'],
            fg_color=self.colors['accent_yellow'],
            hover_color=self.colors['accent_yellow'],
            variable=self.tendencia_var,
            checkbox_width=20,
            checkbox_height=20,
            command=self._ao_marcar_filtro
        )
        self.chk_tendencia.pack(side="left")

        corpo_tendencia = ctk.CTkFrame(content, fg_color="transparent")
        corpo_tendencia.pack(fill="x")
        self.blocos_monitor["tendencia"] = (corpo_tendencia, tend_header)

        # Campos Tendência
        for label, key in [("Média:", "mm_valor"), ("Mercado:", "tendencia")]:
            row = ctk.CTkFrame(corpo_tendencia, fg_color="transparent")
            row.pack(fill="x", pady=5)

            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13),
                        text_color=self.colors['text_muted'], width=90, anchor="w").pack(side="left")

            lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(size=14, weight="bold"),
                              text_color=self.colors['text_secondary'], anchor="e")
            lbl.pack(side="right")
            self.info_labels[key] = lbl

        # Separator
        
        self._criar_menu_param(corpo_tendencia, "Método:", "mm_metodo",
                               {"Simples": 0, "Exponencial": 1,
                                "Suavizada": 2, "Ponderada linear": 3}, "Exponencial")

        for label, key, default in [('Períodos:', 'mm_periodo', '50')]:
            row = ctk.CTkFrame(corpo_tendencia, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12),
                        text_color=self.colors['text_muted'], width=95, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, font=ctk.CTkFont(size=12),
                             fg_color=self.colors['bg_tertiary'],
                             border_color=self.colors['border'],
                             text_color=self.colors['text_primary'],
                             corner_radius=8, height=30, width=95)
            e.pack(side="right")
            e.insert(0, default)
            self.entries_param[key] = e

        ctk.CTkFrame(content, height=1, fg_color=self.colors['border']).pack(fill="x", pady=10)

        # ═══ VOLATILIDADE ═══
        vol_header = ctk.CTkFrame(content, fg_color="transparent")
        vol_header.pack(fill="x", pady=(0, 10))

        self.lbl_atr_status = ctk.CTkLabel(
            vol_header,
            text="DESATIVADO",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=self.colors['accent_red']
        )
        self.lbl_atr_status.pack(side="right")

        # Corpo do bloco: some quando o filtro esta desligado, porque leitura
        # e parametro de filtro inativo nao dizem nada.
        self.chk_atr = ctk.CTkCheckBox(
            vol_header,
            text="VOLATILIDADE",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors['accent_blue'],
            fg_color=self.colors['accent_cyan'],
            hover_color=self.colors['accent_blue'],
            variable=self.atr_var,
            checkbox_width=20,
            checkbox_height=20,
            command=self._alternar_atr
        )
        self.chk_atr.pack(side="left")

        corpo_atr = ctk.CTkFrame(content, fg_color="transparent")
        corpo_atr.pack(fill="x")
        self.blocos_monitor["atr"] = (corpo_atr, vol_header)

        # Campos Volatilidade
        for label, key in [("Movimento:", "atr_pontos")]:
            row = ctk.CTkFrame(corpo_atr, fg_color="transparent")
            row.pack(fill="x", pady=5)

            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13),
                        text_color=self.colors['text_muted'], width=90, anchor="w").pack(side="left")

            lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(size=14, weight="bold"),
                              text_color=self.colors['text_secondary'], anchor="e")
            lbl.pack(side="right")
            self.info_labels[key] = lbl

        for label, key, default in [("Períodos:", "atr_periodo", "14"),
                                    ("Mult. stop:", "atr_mult_sl", "1.5"),
                                    ("Mult. alvo:", "atr_mult_tp", "3.0")]:
            row = ctk.CTkFrame(corpo_atr, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12),
                        text_color=self.colors['text_muted'], width=95, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, font=ctk.CTkFont(size=12),
                             fg_color=self.colors['bg_tertiary'],
                             border_color=self.colors['border'],
                             text_color=self.colors['text_primary'],
                             corner_radius=8, height=30, width=95)
            e.pack(side="right")
            e.insert(0, default)
            self.entries_param[key] = e


    def _criar_coluna_configuracoes(self, parent):
        col_frame = ctk.CTkFrame(parent, fg_color="transparent")
        col_frame.grid(row=0, column=2, sticky="nsew")
        col_frame.grid_rowconfigure(0, weight=1)
        col_frame.grid_rowconfigure(1, weight=0)
        col_frame.grid_columnconfigure(0, weight=1)

        content, card = self._criar_card(col_frame, "CONFIGURAÇÕES", 0, 0, "⚙️")

        # O robô agrupa esses parâmetros como "GERENCIAMENTO DE RISCO";
        # o painel usa o mesmo nome para as duas telas falarem a mesma língua.
        ctk.CTkLabel(
            content,
            text="GESTÃO DE RISCO",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors['accent_cyan']
        ).pack(anchor="w", pady=(0, 10))

        # Lote primeiro; stop e alvo vêm depois do interruptor do ATR,
        # porque é ele que decide se esses dois campos valem alguma coisa.
        self.linhas_risco = {}
        for label, key, default in [("Lote:", "lote", "1.0"),
                                     ("Stop Loss:", "sl", "200"),
                                     ("Take Profit:", "tp", "350")]:
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=3)
            self.linhas_risco[key] = row   # guardada para o ATR poder escondê-la

            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13),
                        text_color=self.colors['text_primary'], width=100, anchor="w").pack(side="left")

            entry = ctk.CTkEntry(
                row,
                font=ctk.CTkFont(size=12),
                fg_color=self.colors['bg_tertiary'],
                border_color=self.colors['border'],
                text_color=self.colors['text_primary'],
                corner_radius=8,
                height=30,
                width=110
            )
            entry.pack(side="right")
            entry.insert(0, default)
            self.entries[key] = entry

        # Stop e alvo pelo ATR: fica aqui, junto dos campos que ele substitui,
        # e não entre os filtros — o ATR não rejeita sinal, só muda as distâncias.
        # Nao empacotada aqui de proposito: uma label vazia continuaria
        # reservando altura e abrindo um vao embaixo do checkbox. Ela so
        # entra na tela quando tem o que dizer (ver _refletir_atr).
        # Trailing Stop
        self.trailing_frame = ctk.CTkFrame(content, fg_color="transparent")
        self.trailing_frame.pack(fill="x", pady=(12, 8))
        trailing_frame = self.trailing_frame

        self.chk_trailing = ctk.CTkCheckBox(
            trailing_frame,
            text="Usar Trailing Stop",
            font=ctk.CTkFont(size=13),
            text_color=self.colors['text_primary'],
            fg_color=self.colors['accent_cyan'],
            hover_color=self.colors['accent_blue'],
            variable=self.trailing_var,
            checkbox_width=20,
            checkbox_height=20,
            command=self._refletir_trailing
        )
        self.chk_trailing.pack(anchor="w")

        # A distância do trailing só aparece com o trailing ligado — campo de
        # ajuste de algo desligado é ruído, e ainda sugere que está valendo.
        self.trailing_pts_frame = ctk.CTkFrame(content, fg_color="transparent")

        ctk.CTkLabel(self.trailing_pts_frame, text="Trailing:", font=ctk.CTkFont(size=13),
                    text_color=self.colors['text_primary'], width=100, anchor="w").pack(side="left")

        self.entry_trailing = ctk.CTkEntry(
            self.trailing_pts_frame,
            font=ctk.CTkFont(size=13),
            fg_color=self.colors['bg_tertiary'],
            border_color=self.colors['border'],
            text_color=self.colors['text_primary'],
            corner_radius=8,
            height=36,
            width=120
        )
        self.entry_trailing.pack(side="right")
        self.entry_trailing.insert(0, "150")

        # Separator
        

        ctk.CTkFrame(content, height=1, fg_color=self.colors['border']).pack(fill="x", pady=(14, 10))
        ctk.CTkLabel(content, text="RSI",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=self.colors['accent_cyan']).pack(anchor="w", pady=(0, 6))

        for label, key, default in [("Períodos:", "rsi_period", "14"),
                                    ("Sobrevenda:", "rsi_os", "40"),
                                    ("Sobrecompra:", "rsi_ob", "60"),
                                    ]:
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13),
                         text_color=self.colors['text_primary'],
                         width=110, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, font=ctk.CTkFont(size=12),
                             fg_color=self.colors['bg_tertiary'],
                             border_color=self.colors['border'],
                             text_color=self.colors['text_primary'],
                             corner_radius=8, height=30, width=110)
            e.pack(side="right")
            e.insert(0, default)
            self.entries_param[key] = e

        self._criar_menu_param(content, "Preço:", "rsi_price",
                               {"Fechamento": 1, "Abertura": 2, "Máxima": 3,
                                "Mínima": 4, "Mediana": 5, "Típico": 6,
                                "Ponderado": 7}, "Fechamento",
                               tamanho=13, cor='text_primary', largura_rotulo=110)

        ctk.CTkFrame(content, height=1, fg_color=self.colors['border']).pack(fill="x", pady=(14, 10))
        ctk.CTkLabel(content, text="EXECUÇÃO",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=self.colors['accent_cyan']).pack(anchor="w", pady=(0, 8))
        row = ctk.CTkFrame(content, fg_color="transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text="Máx. posições:", font=ctk.CTkFont(size=13),
                     text_color=self.colors['text_primary'], width=110, anchor="w").pack(side="left")
        e = ctk.CTkEntry(row, font=ctk.CTkFont(size=12),
                         fg_color=self.colors['bg_tertiary'],
                         border_color=self.colors['border'],
                         text_color=self.colors['text_primary'],
                         corner_radius=8, height=30, width=110)
        e.pack(side="right")
        e.insert(0, "1")
        self.entries_param["max_pos"] = e



        # Botões de ação — fora do card, no mesmo padrão da coluna Monitor
        btn_card = ctk.CTkFrame(col_frame, fg_color=self.colors['bg_secondary'], corner_radius=12)
        btn_card.grid(row=1, column=0, sticky="ew", padx=6, pady=6)

        btn_frame = ctk.CTkFrame(btn_card, fg_color="transparent")
        btn_frame.pack(pady=(12, 6), padx=15, fill="x")

        self.btn_salvar = ctk.CTkButton(
            btn_frame,
            text="💾 SALVAR",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.colors['accent_green'],
            hover_color="#00cc77",
            text_color="#000000",
            corner_radius=8,
            height=42,
            command=self._salvar_config
        )
        self.btn_salvar.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.btn_resetar = ctk.CTkButton(
            btn_frame,
            text="↺ RESETAR",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.colors['text_muted'],
            hover_color="#4b5563",
            text_color="#ffffff",
            corner_radius=8,
            height=42,
            command=self._resetar_config
        )
        self.btn_resetar.pack(side="right", expand=True, fill="x", padx=(4, 0))

        # Botões Diagnóstico e Ajuda
        btn_frame2 = ctk.CTkFrame(btn_card, fg_color="transparent")
        btn_frame2.pack(pady=(6, 12), padx=15, fill="x")

        ctk.CTkButton(
            btn_frame2,
            text="🔍 DIAGNÓSTICO",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.colors['accent_blue'],
            hover_color="#2563eb",
            corner_radius=8,
            height=42,
            command=self._diagnostico
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))

        ctk.CTkButton(
            btn_frame2,
            text="❓ AJUDA",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.colors['accent_purple'],
            hover_color="#7c3aed",
            corner_radius=8,
            height=42,
            command=self._ajuda
        ).pack(side="right", expand=True, fill="x", padx=(4, 0))

        # Só confirma ações (salvar, resetar) e some depois. A data do pregão
        # saiu daqui: ela agora tem lugar próprio no card Monitor.
        self.lbl_status_config = ctk.CTkLabel(
            btn_card,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=self.colors['text_muted']
        )


    # ═══════════════════════════════════════════════════════════════
    # FUNÇÕES DE DADOS
    # ═══════════════════════════════════════════════════════════════

    def _ler_dados(self):
        """
        Lê o arquivo JSON exportado pelo EA.

        Usa retry (3 tentativas) porque o EA pode estar escrevendo no momento.
        Isso evita erros de "arquivo em uso" ou JSON incompleto.
        """
        if not os.path.exists(self.data_file):
            return None

        # Tenta 3x com intervalo de 100ms entre tentativas
        for _ in range(3):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    conteudo = f.read()
                    if conteudo.strip():
                        dados = json.loads(conteudo)
                        # JSON valido que nao seja objeto (lista, numero) faria
                        # todo o painel chamar .get() em algo que nao tem: trata
                        # como arquivo invalido em vez de falhar calado adiante.
                        return dados if isinstance(dados, dict) else None
            except (PermissionError, json.JSONDecodeError):
                time.sleep(0.1)  # Arquivo em uso, aguarda
            except Exception as e:
                print(f"Erro ao ler dados: {e}")
                break
        return None

    def _atualizar_dados(self):
        """
        Loop principal de atualização - roda a cada 250ms.

        1. Verifica se o modo mudou (LIVE <-> BACKTEST)
        2. Lê dados do arquivo JSON exportado pelo EA
        3. Atualiza todos os labels e indicadores visuais
        4. Sincroniza campos de configuração (apenas se não tiverem foco)
        """
        try:
            # Permite alternar entre LIVE e BACKTEST sem reiniciar
            novo_modo = self._detectar_modo()
            if novo_modo != self.modo_atual:
                self.modo_atual = novo_modo
                self._atualizar_arquivos()
                self.modo_badge.configure(text=f"● {self.modo_atual}")
                self.checkboxes_sincronizados = False

                # Mostra/oculta Lucro Total baseado no modo
                if self.modo_atual == "BACKTEST":
                    self.lucro_total_frame.pack(fill="x", padx=12, pady=(5, 10))
                else:
                    self.lucro_total_frame.pack_forget()

            dados = self._ler_dados()
            agora = time.time()

            if dados:
                novo_timestamp = dados.get('timestamp', '')

                # Verifica se recebeu dados NOVOS (timestamp diferente)
                if novo_timestamp != self.ultimo_timestamp:
                    self.ultimo_timestamp = novo_timestamp
                    self.ultima_atualizacao_real = agora  # Marca momento real

                # Em BACKTEST: parar de receber quer dizer que o teste acabou,
                # e não que algo quebrou — por isso a mensagem é outra.
                # Em LIVE: usa timeout para detectar desconexão
                if self.modo_atual == "BACKTEST":
                    parado = (self.ultima_atualizacao_real is not None and
                              (agora - self.ultima_atualizacao_real) > self.timeout_backtest)
                    if parado:
                        self.conexao_ativa = False
                        self.lbl_conexao.configure(text="FINALIZADO",
                                                   text_color=self.colors['accent_cyan'])
                        self.status_indicator.configure(fg_color=self.colors['accent_cyan'])
                        self.status_badge.configure(text="● TESTE FINALIZADO",
                                                    text_color=self.colors['accent_cyan'],
                                                    fg_color=self.colors['bg_tertiary'])
                        self.lbl_sinal_status.configure(
                            text="Teste concluído", text_color=self.colors['accent_cyan'])
                        self._mostrar_data(dados)
                        self._refletir_controles(dados, finalizado=True)
                        self.after(250, self._atualizar_dados)
                        return

                    # BACKTEST rodando: dados chegando
                    self.conexao_ativa = True
                    self.lbl_conexao.configure(text="CONECTADO", text_color=self.colors['accent_green'])
                    self.status_indicator.configure(fg_color=self.colors['accent_green'])

                    # Status do robô direto do EA
                    status = dados.get('status', 'ATIVO')
                    if status == "ATIVO":
                        self.status_badge.configure(text="● ATIVO", text_color=self.colors['accent_green'],
                                                   fg_color=self.colors['bg_tertiary'])
                    elif status == "PAUSADO":
                        self.status_badge.configure(text="● PAUSADO", text_color=self.colors['accent_yellow'],
                                                   fg_color=self.colors['bg_tertiary'])
                    else:
                        self.status_badge.configure(text=f"● {status}", text_color=self.colors['accent_cyan'],
                                                   fg_color=self.colors['bg_tertiary'])
                else:
                    # LIVE: Verifica timeout para detectar desconexão real
                    if self.ultima_atualizacao_real:
                        tempo_sem_dados = agora - self.ultima_atualizacao_real
                        if tempo_sem_dados > self.timeout_conexao:
                            # EA parou de enviar dados (travou ou fechou)
                            self.conexao_ativa = False
                            self.lbl_conexao.configure(text="DESCONECTADO", text_color=self.colors['accent_red'])
                            self.status_indicator.configure(fg_color=self.colors['accent_red'])
                            self.status_badge.configure(text="● DESCONECTADO", text_color=self.colors['accent_red'],
                                                       fg_color=self.colors['bg_tertiary'])
                            self.lbl_sinal_status.configure(text="")
                        else:
                            # EA está enviando dados normalmente
                            self.conexao_ativa = True
                            self.lbl_conexao.configure(text="CONECTADO", text_color=self.colors['accent_green'])
                            self.status_indicator.configure(fg_color=self.colors['accent_green'])

                            # Status do robô (só mostra se conectado)
                            status = dados.get('status', 'DESCONHECIDO')
                            if status == "ATIVO":
                                self.status_badge.configure(text="● ATIVO", text_color=self.colors['accent_green'],
                                                           fg_color=self.colors['bg_tertiary'])
                            elif status == "PAUSADO":
                                self.status_badge.configure(text="● PAUSADO", text_color=self.colors['accent_yellow'],
                                                           fg_color=self.colors['bg_tertiary'])
                            else:
                                self.status_badge.configure(text=f"● {status}", text_color=self.colors['accent_cyan'],
                                                           fg_color=self.colors['bg_tertiary'])
                    else:
                        # Primeira vez recebendo dados
                        self.ultima_atualizacao_real = agora
                        self.conexao_ativa = True
                        self.lbl_conexao.configure(text="CONECTADO", text_color=self.colors['accent_green'])
                        self.status_indicator.configure(fg_color=self.colors['accent_green'])

                # Atualiza dados visuais (independente do timeout, mostra últimos dados)
                if self.conexao_ativa:

                    # Atualiza labels
                    self.info_labels['ativo'].configure(text=dados.get('ativo', '--'))
                    self.info_labels['posicoes'].configure(text=str(dados.get('posicoes', 0)))
                    self.info_labels['rsi'].configure(text=f"{dados.get('rsi', 0):.2f}")

                    # Lucro dia
                    lucro_dia = dados.get('lucro_dia', 0)
                    cor_lucro = self.colors['accent_green'] if lucro_dia >= 0 else self.colors['accent_red']
                    self.info_labels['lucro_dia'].configure(text=f"R$ {lucro_dia:.2f}", text_color=cor_lucro)

                    # Saldo
                    self.info_labels['saldo'].configure(text=f"R$ {dados.get('saldo', 0):.2f}")

                    # Lucro aberto
                    lucro_aberto = dados.get('lucro_aberto', 0)
                    cor_aberto = self.colors['accent_green'] if lucro_aberto >= 0 else self.colors['accent_red']
                    self.info_labels['lucro_aberto'].configure(text=f"R$ {lucro_aberto:.2f}", text_color=cor_aberto)

                    # Lucro total (apenas em BACKTEST)
                    if self.modo_atual == "BACKTEST":
                        lucro_total = dados.get('lucro_total', 0)
                        cor_total = self.colors['accent_green'] if lucro_total >= 0 else self.colors['accent_red']
                        self.info_labels['lucro_total'].configure(text=f"R$ {lucro_total:.2f}", text_color=cor_total)

                    # Agressão
                    usar_agressao = dados.get('usar_agressao', False)
                    self.lbl_agressao_status.configure(
                        text="ATIVADO" if usar_agressao else "DESATIVADO",
                        text_color=self.colors['accent_green'] if usar_agressao else self.colors['accent_red']
                    )

                    if usar_agressao:
                        self.info_labels['agressao_compra'].configure(text=f"{dados.get('agressao_compra', 0):.1f}%", text_color=self.colors['accent_cyan'])
                        self.info_labels['agressao_venda'].configure(text=f"{dados.get('agressao_venda', 0):.1f}%", text_color=self.colors['accent_cyan'])
                        self.info_labels['agressao_vol'].configure(text=f"{dados.get('agressao_vol', 0):.0f}", text_color=self.colors['accent_cyan'])
                        direcao = dados.get('agressao_direcao', 'NEUTRO')
                        cor_dir = self.colors['accent_green'] if direcao == "COMPRA" else self.colors['accent_red'] if direcao == "VENDA" else self.colors['text_muted']
                        # Capitalização normal em vez de caixa alta: em bold,
                        # maiúscula pesa mais que os números da mesma linha.
                        rotulo_dir = direcao or "--"
                        self.info_labels['agressao_direcao'].configure(text=rotulo_dir, text_color=cor_dir)
                    else:
                        for k in ['agressao_compra', 'agressao_venda', 'agressao_vol']:
                            self.info_labels[k].configure(text="--", text_color=self.colors['text_muted'])
                        self.info_labels['agressao_direcao'].configure(text="--", text_color=self.colors['text_muted'])

                    # Volume Profile
                    usar_vp = dados.get('usar_volume_profile', False)
                    self.lbl_vp_status.configure(
                        text="ATIVADO" if usar_vp else "DESATIVADO",
                        text_color=self.colors['accent_green'] if usar_vp else self.colors['accent_red']
                    )

                    if usar_vp:
                        self.info_labels['vp_poc'].configure(text=f"{dados.get('vp_poc', 0):.2f}", text_color=self.colors['accent_cyan'])
                        self.info_labels['vp_vah'].configure(text=f"{dados.get('vp_vah', 0):.2f}", text_color=self.colors['accent_cyan'])
                        self.info_labels['vp_val'].configure(text=f"{dados.get('vp_val', 0):.2f}", text_color=self.colors['accent_cyan'])
                        zona = dados.get('vp_zona', '') or ''
                        # caixa alta, mas sem underscore: ACIMA_POC -> ACIMA DO POC
                        rotulo_zona = {"ACIMA_POC": "ACIMA DO POC",
                                       "ABAIXO_POC": "ABAIXO DO POC",
                                       "NO_POC": "NO POC",
                                       "INDEFINIDO": "--"}.get(zona, zona or "--")
                        self.info_labels['vp_zona'].configure(text=rotulo_zona, text_color=self.colors['accent_cyan'])
                    else:
                        for k in ['vp_poc', 'vp_vah', 'vp_val']:
                            self.info_labels[k].configure(text="--", text_color=self.colors['text_muted'])
                        self.info_labels['vp_zona'].configure(text="--", text_color=self.colors['text_muted'])

                    # Tendência (média móvel)
                    usar_tend = dados.get('usar_tendencia', False)
                    self.lbl_tend_status.configure(
                        text="ATIVADO" if usar_tend else "DESATIVADO",
                        text_color=self.colors['accent_green'] if usar_tend else self.colors['accent_red']
                    )

                    if usar_tend:
                        self.info_labels['mm_valor'].configure(text=f"{dados.get('mm_valor', 0):.2f}", text_color=self.colors['accent_cyan'])
                        # Verde quando o mercado sobe, vermelho quando cai: mesma
                        # semântica de cor que o resto do painel usa para compra/venda
                        tend = dados.get('tendencia', '') or '--'
                        cor_tend = (self.colors['accent_green'] if tend == "ALTA"
                                    else self.colors['accent_red'] if tend == "BAIXA"
                                    else self.colors['text_muted'])
                        rotulo = {"ALTA": "SUBINDO", "BAIXA": "CAINDO"}.get(tend, "--")
                        self.info_labels['tendencia'].configure(text=rotulo, text_color=cor_tend)
                    else:
                        self.info_labels['mm_valor'].configure(text="--", text_color=self.colors['text_muted'])
                        self.info_labels['tendencia'].configure(text="--", text_color=self.colors['text_muted'])

                    # Volatilidade (ATR)
                    usar_atr = dados.get('usar_atr', False)
                    self.lbl_atr_status.configure(
                        text="ATIVADO" if usar_atr else "DESATIVADO",
                        text_color=self.colors['accent_green'] if usar_atr else self.colors['accent_red']
                    )

                    if usar_atr:
                        self.info_labels['atr_pontos'].configure(text=f"{dados.get('atr_pontos', 0):.0f} pts", text_color=self.colors['accent_cyan'])
                    else:
                        self.info_labels['atr_pontos'].configure(text="--", text_color=self.colors['text_muted'])

                    # Data do pregão que o robô está vendo.
                    # No backtest é tempo simulado, e vem em roxo (a mesma cor
                    # do selo BACKTEST) para ninguém confundir com data real.
                    self._mostrar_data(dados)

                    # Sinal status
                    self.lbl_sinal_status.configure(text=self._texto_sinal(dados.get('sinal_status', '')))

                    # Sincroniza campos, menos o que estiver sendo digitado.
                    # focus_get() devolve o Entry interno do Tk, não o CTkEntry —
                    # comparar só com o CTkEntry nunca casa, e o campo era
                    # reescrito a cada 250 ms enquanto a pessoa digitava.
                    foco = self.focus_get()
                    entry_widgets = [self.entries['lote'], self.entries['sl'],
                                     self.entries['tp'], self.entry_trailing]
                    entry_widgets += list(self.entries_param.values())
                    internos = [w._entry for w in entry_widgets if hasattr(w, '_entry')]
                    if foco not in entry_widgets and foco not in internos:
                        self.entries['lote'].delete(0, 'end')
                        self.entries['lote'].insert(0, str(dados.get('lote', 1.0)))
                        self.entries['sl'].delete(0, 'end')
                        self.entries['sl'].insert(0, str(int(dados.get('stoploss', 200))))
                        self.entries['tp'].delete(0, 'end')
                        self.entries['tp'].insert(0, str(int(dados.get('takeprofit', 350))))
                        self.entry_trailing.delete(0, 'end')
                        self.entry_trailing.insert(0, str(int(dados.get('trailing_pontos', 150))))

                        # Parâmetros do robô: o EA publica cada um como p_<nome>.
                        # Sem valor publicado o campo fica como está, para não
                        # apagar o que a pessoa acabou de digitar.
                        for chave, (menu, opcoes) in self.menus_param.items():
                            valor = dados.get('p_' + chave)
                            if valor is None:
                                continue
                            for rotulo, num in opcoes.items():
                                if num == int(valor):
                                    if menu.get() != rotulo:
                                        menu.set(rotulo)
                                    break

                        for chave, campo in self.entries_param.items():
                            valor = dados.get('p_' + chave)
                            if valor is None:
                                continue
                            texto = str(int(valor)) if float(valor) == int(float(valor)) else str(valor)
                            if campo.get() != texto:
                                campo.delete(0, 'end')
                                campo.insert(0, texto)

                        if not self.checkboxes_sincronizados:
                            self.trailing_var.set(dados.get('usar_trailing', True))
                            self.agressao_var.set(dados.get('usar_agressao', False))
                            self.volume_profile_var.set(dados.get('usar_volume_profile', False))
                            self.tendencia_var.set(dados.get('usar_tendencia', False))
                            self.atr_var.set(dados.get('usar_atr', False))
                            self.checkboxes_sincronizados = True

                    # Com o ATR ligado, quem manda no stop e no alvo é ele.
                    # Mostra a distância que está valendo de verdade, para os
                    # campos não exibirem um número que o robô não está usando.
                    self._refletir_atr(dados)
                    self._refletir_trailing()
                    self._refletir_expansao()
                    self._refletir_controles(dados)

                    pass  # a data do pregão é mostrada no card Monitor
            else:
                # Não há arquivo de dados - EA nunca foi iniciado ou arquivo foi deletado
                self.conexao_ativa = False
                self.lbl_conexao.configure(text="DESCONECTADO", text_color=self.colors['accent_red'])
                self.status_indicator.configure(fg_color=self.colors['accent_red'])
                self.status_badge.configure(text="● DESCONECTADO EA", text_color=self.colors['accent_yellow'],
                                           fg_color=self.colors['bg_tertiary'])
                self.lbl_sinal_status.configure(text="")

        except Exception as e:
            print(f"Erro: {e}")

        self.after(250, self._atualizar_dados)

    def _enviar_comando(self, comando):
        """
        Envia comando para o EA via arquivo de texto.

        Formato do arquivo:
        - Linha 1: comando (ex: PAUSAR, FECHAR_TUDO, SALVAR_CONFIG:...)
        - Linha 2: timestamp (para o EA saber se é comando novo)

        O EA lê, processa e deleta o arquivo de comandos.
        """
        try:
            timestamp = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
            with open(self.command_file, "w", encoding="utf-8") as f:
                f.write(f"{comando}\n{timestamp}")
            return True
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao enviar comando: {e}")
            return False

    def _pausar_retomar(self):
        self._enviar_comando("PAUSAR")

    def _fechar_tudo(self):
        if messagebox.askyesno("Confirmar", "Fechar todas as posições?"):
            self._enviar_comando("FECHAR_TUDO")

    def _parar_ea(self):
        """Para o EA no MetaTrader e fecha o painel."""
        if messagebox.askyesno("Parar EA", "Isso vai remover o EA do gráfico e fechar o painel.\n\nDeseja continuar?"):
            self._enviar_comando("PARAR_EA")
            self.after(500, self.destroy)  # Aguarda 500ms para o comando ser enviado

    def _avisar_config(self, texto, cor, segundos=3):
        """Mostra uma confirmação embaixo dos botões e some depois."""
        try:
            self.lbl_status_config.configure(text=texto, text_color=cor)
            if not self.lbl_status_config.winfo_ismapped():
                self.lbl_status_config.pack(pady=(0, 10))
            self.after(segundos * 1000, self._limpar_aviso_config)
        except Exception:
            pass

    def _limpar_aviso_config(self):
        try:
            if self.lbl_status_config.winfo_ismapped():
                self.lbl_status_config.pack_forget()
        except Exception:
            pass

    def _texto_sinal(self, bruto):
        """
        Enxuga o status para caber ao lado do badge.

        O EA manda "RSI neutro (45.4)"; o número sai porque já existe a linha
        RSI logo abaixo, e repetir só rouba espaço.
        """
        texto = re.sub(r"\s*\([^)]*\)", "", (bruto or "").strip())
        return texto or "Aguardando sinal"

    def _refletir_trailing(self):
        """Mostra a distância do trailing apenas quando ele está ligado."""
        try:
            if self.trailing_var.get():
                if not self.trailing_pts_frame.winfo_ismapped():
                    # 'after' é obrigatório: pack() sem âncora recoloca o widget
                    # no fim do container, e ele reapareceria depois dos botões.
                    self.trailing_pts_frame.pack(fill="x", pady=6, after=self.trailing_frame)
            else:
                if self.trailing_pts_frame.winfo_ismapped():
                    self.trailing_pts_frame.pack_forget()
        except Exception:
            pass

    def _mostrar_data(self, dados):
        """
        Mostra a data do pregão que o robô está lendo.

        Chega do EA como "2025.01.31 09:18:40" e vira "31/01/2025 09:18",
        que é como a data se lê em português. Em backtest o tempo é simulado,
        então a cor acompanha o selo BACKTEST.
        """
        try:
            bruto = (dados.get('timestamp') or '').strip()
            if not bruto:
                self.info_labels['data_pregao'].configure(text="--", text_color=self.colors['text_muted'])
                return

            data_hora = bruto.split(' ')
            partes = data_hora[0].split('.')
            if len(partes) == 3:
                texto = f"{partes[2]}/{partes[1]}/{partes[0]}"
            else:
                texto = data_hora[0]
            if len(data_hora) > 1:
                texto += "  " + data_hora[1][:5]   # sem os segundos: muda rápido demais para ler

            cor = (self.colors['accent_purple'] if self.modo_atual == "BACKTEST"
                   else self.colors['accent_cyan'])
            self.info_labels['data_pregao'].configure(text=texto, text_color=cor)
        except Exception:
            pass

    def _validar_numero(self, texto):
        """
        Deixa passar só número no campo.

        Vazio é permitido — senão não dá para apagar e digitar de novo.
        Vírgula é aceita e vira ponto na hora de ler, porque em português
        é natural digitar 1,5.
        """
        if texto.strip() == "":
            return True
        try:
            float(texto.replace(",", "."))
            return True
        except ValueError:
            return False

    def _limitar_a_numeros(self):
        """Aplica a validação nos campos de lote, stop, alvo e trailing."""
        checagem = (self.register(self._validar_numero), "%P")
        campos = [self.entries.get('lote'), self.entries.get('sl'),
                  self.entries.get('tp'), getattr(self, 'entry_trailing', None)]
        for campo in campos:
            if campo is None:
                continue
            try:
                campo.configure(validate="key", validatecommand=checagem)
            except Exception:
                pass

    def _criar_menu_param(self, pai, rotulo, chave, opcoes, padrao,
                          tamanho=12, cor='text_muted', largura_rotulo=95):
        """
        Campo de escolha (media movel, preco do RSI).

        Guarda o mapa rotulo -> numero porque o robo espera o valor do enum,
        nao o texto que aparece na tela.
        """
        row = ctk.CTkFrame(pai, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=rotulo, font=ctk.CTkFont(size=tamanho),
                     text_color=self.colors[cor], width=largura_rotulo, anchor="w").pack(side="left")
        menu = ctk.CTkOptionMenu(
            row, values=list(opcoes.keys()),
            font=ctk.CTkFont(size=12),
            fg_color=self.colors['bg_tertiary'],
            button_color=self.colors['bg_hover'],
            button_hover_color=self.colors['border'],
            text_color=self.colors['text_primary'],
            dropdown_fg_color=self.colors['bg_tertiary'],
            dropdown_text_color=self.colors['text_primary'],
            corner_radius=8, height=30, width=140
        )
        menu.set(padrao)
        menu.pack(side="right")
        self.menus_param[chave] = (menu, opcoes)
        return menu

    def _ajustar_altura_janela(self):
        """
        Faz a janela seguir o conteudo em vez de depender de um numero fixo.

        Mede a coluna mais alta ja montada e redimensiona. Assim, qualquer
        campo acrescentado depois continua cabendo sem ninguem lembrar de
        atualizar uma constante.
        """
        try:
            self.update_idletasks()
            # reqheight da janela ja soma cabecalho, cards, botoes e margens.
            # Medir so a coluna mais alta deixava de fora os 93px do topo e
            # cortava a ultima secao.
            preciso = self.winfo_reqheight()
            if preciso <= 0:
                return
            teto = self.winfo_screenheight() - 80

            # A janela nasce no tamanho do conteudo e dai em diante so cresce,
            # ate o teto da tela. Encolher ao fechar um bloco fazia a coluna de
            # configuracoes perder a ultima secao, porque a altura passava a ser
            # ditada pelo monitoramento vazio.
            if not hasattr(self, "_altura_minima"):
                self._altura_minima = min(preciso, teto)

            alvo = min(max(preciso, self._altura_minima, self.winfo_height()), teto)
            if abs(self.winfo_height() - alvo) > 8:
                self.geometry(f"{self.winfo_width()}x{alvo}")
        except Exception:
            pass   # medir a janela nunca pode derrubar o painel

    def _ao_marcar_filtro(self):
        """
        Responde ao clique na hora, sem esperar o proximo dado do robo.

        O laco de atualizacao so roda com conexao ativa; sem isto, marcar ou
        desmarcar com o robo parado nao mexia na tela.
        """
        self._refletir_expansao()

    def _alternar_atr(self):
        """Mostra ou esconde Stop Loss e Take Profit assim que o ATR é clicado."""
        self._refletir_expansao()
        self._refletir_atr()

    def _refletir_expansao(self):
        """
        Abre o bloco do filtro ligado e fecha o dos desligados.

        Parametro e leitura de filtro inativo nao informam nada, e o espaco
        que eles ocupam e justamente o que falta para tudo caber sem rolagem.
        """
        estados = {
            "agressao":  self.agressao_var.get(),
            "vp":        self.volume_profile_var.get(),
            "tendencia": self.tendencia_var.get(),
            "atr":       self.atr_var.get(),
        }
        mudou = False
        for nome, ligado in estados.items():
            par = self.blocos_monitor.get(nome)
            if par is None:
                continue
            corpo, cabecalho = par
            visivel = bool(corpo.winfo_manager())
            if ligado and not visivel:
                # after= e o que devolve o bloco para baixo do proprio titulo;
                # sem isso o pack recoloca no fim da coluna.
                corpo.pack(fill="x", after=cabecalho)
                mudou = True
            elif not ligado and visivel:
                corpo.pack_forget()
                mudou = True

        if mudou:
            self._ajustar_altura_janela()
            if hasattr(self, "_ajustar_barra_card"):
                self.after(50, self._ajustar_barra_card)

    def _refletir_controles(self, dados=None, finalizado=False):
        """
        Deixa os botões contarem a verdade sobre o que dá para fazer agora.

        - Pausar vira Retomar quando o robô está pausado: o botão diz o que
          vai acontecer ao clicar, não o estado em que se está.
        - Fechar tudo só liga com posição aberta — sem posição não há o que fechar.
        - Parar, Salvar e Resetar dependem do robô estar escutando.
        - Diagnóstico e Ajuda nunca desligam: é quando algo deu errado que
          você mais precisa deles.
        """
        try:
            dados = dados or {}
            vivo = bool(self.conexao_ativa) and not finalizado
            pausado = str(dados.get('status', '')).upper() == "PAUSADO"
            try:
                posicoes = int(float(dados.get('posicoes', 0) or 0))
            except (TypeError, ValueError):
                posicoes = 0

            if pausado:
                self.btn_pausar.configure(text="▶ RETOMAR",
                                          fg_color=self.colors['accent_green'],
                                          hover_color="#00cc77",
                                          text_color="#000000")
            else:
                self.btn_pausar.configure(text="⏸ PAUSAR",
                                          fg_color=self.colors['accent_yellow'],
                                          hover_color="#e6b800",
                                          text_color="#000000")

            self.btn_pausar.configure(state="normal" if vivo else "disabled")
            self.btn_fechar.configure(state="normal" if (vivo and posicoes > 0) else "disabled")
            for botao in (self.btn_parar, self.btn_salvar, self.btn_resetar):
                botao.configure(state="normal" if vivo else "disabled")
        except Exception:
            pass

    def _refletir_atr(self, dados=None):
        """
        Mostra ou esconde Stop Loss e Take Profit conforme o ATR.

        Com o ATR marcado quem define as distâncias é a volatilidade, então os
        dois campos somem: campo que não vale nada só ocupa espaço e engana.
        Segue o checkbox, e não o robô, para responder já no clique.
        """
        try:
            usar_atr = bool(self.atr_var.get())
            anterior = self.linhas_risco.get('lote')

            for k in ('sl', 'tp'):
                linha = self.linhas_risco.get(k)
                if linha is None:
                    continue
                if usar_atr:
                    if linha.winfo_ismapped():
                        linha.pack_forget()
                else:
                    if not linha.winfo_ismapped():
                        # 'after' devolve a linha ao lugar certo, não ao fim
                        linha.pack(fill="x", pady=6, after=anterior)
                    if k in self.entries:
                        self.entries[k].configure(state="normal",
                                                  text_color=self.colors['text_primary'])
                    anterior = linha
        except Exception:
            pass

    # Faixa aceita por parametro: (minimo, maximo, so inteiro, nome na tela).
    # Sem isto o painel aceitava periodo negativo e lote de um bilhao, e mandava
    # para o robo, que so descobria o problema operando.
    LIMITES = {
        "lote":         (0.01, 1000, False, "Lote"),
        "sl":           (1, 100000, True,  "Stop Loss"),
        "tp":           (1, 100000, True,  "Take Profit"),
        "trailing_pts": (1, 100000, True,  "Trailing"),
        "rsi_period":   (1, 500,   True,  "Períodos do RSI"),
        "rsi_os":       (0, 100,   False, "Sobrevenda"),
        "rsi_ob":       (0, 100,   False, "Sobrecompra"),
        "mm_periodo":   (1, 1000,  True,  "Períodos da média"),
        "atr_periodo":  (1, 500,   True,  "Períodos do ATR"),
        "atr_mult_sl":  (0.1, 50,  False, "Multiplicador do stop"),
        "atr_mult_tp":  (0.1, 50,  False, "Multiplicador do alvo"),
        "agr_janela":   (1, 3600,  True,  "Janela do fluxo"),
        "agr_volmin":   (0, 1000000, False, "Volume mínimo"),
        "agr_pctmin":   (0.01, 1,  False, "Confirmação do fluxo"),
        "vp_barras":    (1, 5000,  True,  "Candles do perfil"),
        "vp_passo":     (1, 1000,  True,  "Agrupamento do perfil"),
        "vp_margem":    (0, 10000, False, "Zona do POC"),
        "max_pos":      (1, 100,   True,  "Máx. posições"),
    }

    def _salvar_config(self):
        """
        Envia os parâmetros ao robô no formato chave=valor.

        O robô aplica na hora, inclusive períodos de RSI, média e ATR, que
        exigem recriar o indicador. Campo vazio ou inválido é ignorado, e o
        robô mantém o valor que já estava valendo.
        """
        try:
            pares = {
                'lote':         float(self.entries['lote'].get().replace(',', '.')),
                'sl':           float(self.entries['sl'].get().replace(',', '.')),
                'tp':           float(self.entries['tp'].get().replace(',', '.')),
                'trailing_pts': float(self.entry_trailing.get().replace(',', '.')),
                'trailing':          1 if self.trailing_var.get() else 0,
                'usar_agressao':     1 if self.agressao_var.get() else 0,
                'usar_volume_profile': 1 if self.volume_profile_var.get() else 0,
                'usar_tendencia':    1 if self.tendencia_var.get() else 0,
                'usar_atr':          1 if self.atr_var.get() else 0,
            }
        except ValueError:
            messagebox.showerror("Valor inválido",
                                 "Lote, stop, alvo e stop móvel precisam ser números.")
            return

        for chave, campo in self.entries_param.items():
            texto = campo.get().strip().replace(',', '.')
            if not texto:
                continue
            try:
                pares[chave] = float(texto)
            except ValueError:
                lim = self.LIMITES.get(chave)
                messagebox.showerror("Valor inválido",
                                     f"{lim[3] if lim else chave} precisa ser um número.")
                return

        # Faixa aceita: barra aqui, antes de chegar no robo
        for chave, valor in pares.items():
            lim = self.LIMITES.get(chave)
            if lim is None:
                continue
            minimo, maximo, inteiro, nome = lim
            if valor < minimo or valor > maximo:
                messagebox.showerror(
                    "Fora da faixa",
                    f"{nome} aceita de {minimo} a {maximo}.\nVocê digitou {valor:g}.")
                return
            if inteiro and float(valor) != int(valor):
                messagebox.showerror("Valor inválido", f"{nome} precisa ser um número inteiro.")
                return

        if pares.get("rsi_os", 0) >= pares.get("rsi_ob", 100):
            messagebox.showerror(
                "Níveis invertidos",
                "A sobrevenda precisa ser menor que a sobrecompra.\n"
                f"Você colocou {pares.get('rsi_os'):g} e {pares.get('rsi_ob'):g}.")
            return

        for chave, (menu, opcoes) in self.menus_param.items():
            pares[chave] = opcoes.get(menu.get(), 0)

        comando = "SALVAR_CONFIG:" + ";".join(f"{k}={v}" for k, v in pares.items())
        if self._enviar_comando(comando):
            self._avisar_config(f"✓ {len(pares)} parâmetros aplicados", self.colors['accent_green'])

    def _resetar_config(self):
        if messagebox.askyesno("Confirmar", "Resetar para valores originais?"):
            self._enviar_comando("RESETAR_CONFIG")
            # Força re-sincronização dos checkboxes e campos na próxima atualização
            self.checkboxes_sincronizados = False
            self._avisar_config("↺ Configurações resetadas", self.colors['accent_yellow'], 2)

    def _preparar_card_rolavel(self, area):
        """
        Deixa o card rolar de verdade e sem barra sobrando.

        Duas coisas que o CTkScrollableFrame nao faz sozinho: a barra fica
        visivel mesmo quando nao ha o que rolar, e a roda do mouse nao mexe
        nada no Tk 9 do macOS, onde o evento chega como <TouchpadScroll>.
        """
        canvas = area._parent_canvas
        barra = area._scrollbar

        def precisa_rolar():
            try:
                return canvas.yview() != (0.0, 1.0)
            except Exception:
                return False

        def ajustar_barra(_=None):
            try:
                if precisa_rolar():
                    if not barra.winfo_ismapped():
                        barra.grid()
                else:
                    if barra.winfo_ismapped():
                        barra.grid_remove()
                    canvas.yview_moveto(0)
            except Exception:
                pass

        def sob_o_mouse():
            try:
                x, y = self.winfo_pointerxy()
                dentro_x = area.winfo_rootx() <= x <= area.winfo_rootx() + area.winfo_width()
                dentro_y = area.winfo_rooty() <= y <= area.winfo_rooty() + area.winfo_height()
                return dentro_x and dentro_y
            except Exception:
                return False

        def desliza(passos):
            if precisa_rolar() and sob_o_mouse():
                canvas.yview("scroll", passos, "units")

        def com_sinal(valor):
            return valor - 65536 if valor >= 32768 else valor

        def touchpad(evento):
            bruto = getattr(evento, "delta", 0) or 0
            dy = com_sinal((bruto >> 16) & 0xFFFF)
            if dy:
                desliza(dy)

        def roda(evento):
            d = getattr(evento, "delta", 0) or 0
            if d:
                desliza(-int(d))

        ligar_evento(self, "<TouchpadScroll>", touchpad, todos=True)
        self.bind_all("<MouseWheel>", roda, add=True)
        self.bind_all("<Button-4>", lambda e: desliza(-1), add=True)
        self.bind_all("<Button-5>", lambda e: desliza(1), add=True)
        area.bind("<Configure>", ajustar_barra, add=True)
        canvas.bind("<Configure>", ajustar_barra, add=True)
        self._ajustar_barra_card = ajustar_barra
        self.after(300, ajustar_barra)

    def _rolar_com_mouse(self, janela, area):
        """
        Liga a rolagem numa janela secundária.

        No Tk 9 do macOS o <MouseWheel> deixou de ser disparado: trackpad e
        roda chegam como <TouchpadScroll>, cujo delta traz os dois eixos
        empacotados num inteiro só (16 bits baixos = x, altos = y).
        O CustomTkinter 6 ainda escuta apenas o evento antigo, então sem isto
        a roda não rola nada — só sobra arrastar a barra.
        """
        def desliza(passos):
            try:
                canvas = area._parent_canvas
                if canvas.yview() != (0.0, 1.0):
                    canvas.yview("scroll", passos, "units")
            except Exception:
                pass

        def com_sinal(valor):
            return valor - 65536 if valor >= 32768 else valor

        def touchpad(evento):
            # delta traz os dois eixos empacotados; o vertical vem nos bits altos.
            # y positivo = rolar para baixo, por isso o valor entra sem inverter.
            bruto = getattr(evento, "delta", 0) or 0
            dy = com_sinal((bruto >> 16) & 0xFFFF)
            if dy:
                desliza(dy)

        def roda(evento):
            d = getattr(evento, "delta", 0) or 0
            if d:
                desliza(-int(d))

        ligar_evento(janela, "<TouchpadScroll>", touchpad)
        ligar_evento(janela, "<TouchpadScroll>", touchpad, todos=True)
        janela.bind("<MouseWheel>", roda, add=True)          # Tk 8 e outros sistemas
        janela.bind("<Button-4>", lambda e: desliza(-1), add=True)
        janela.bind("<Button-5>", lambda e: desliza(1), add=True)

    def _diagnostico(self):
        """
        Estado da ligação entre o painel e o robô.

        Segue a mesma estrutura dos cards: título à esquerda, linhas de
        rótulo e valor alinhadas nas bordas, fio separando os blocos.
        """
        diag = ctk.CTkToplevel(self)
        diag.title("Diagnóstico")
        diag.geometry("440x310")
        diag.configure(fg_color=self.colors['bg_primary'])
        diag.resizable(False, False)

        container = ctk.CTkFrame(diag, fg_color=self.colors['bg_secondary'], corner_radius=16)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        corpo = ctk.CTkFrame(container, fg_color="transparent")
        corpo.pack(fill="x", padx=22, pady=(18, 0))

        ctk.CTkLabel(
            corpo,
            text="🔍 DIAGNÓSTICO",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors['accent_cyan'],
            anchor="w"
        ).pack(fill="x")

        ctk.CTkFrame(corpo, height=1, fg_color=self.colors['border']).pack(fill="x", pady=(10, 4))

        conectado = self.conexao_ativa
        linhas = [
            ("Conexão:", "CONECTADO" if conectado else "DESCONECTADO",
             self.colors['accent_green'] if conectado else self.colors['accent_red']),
            ("Modo:", self.modo_atual, self.colors['accent_purple']
             if self.modo_atual == "BACKTEST" else self.colors['accent_cyan']),
            ("Arquivo:", f"rsi_data_{self.modo_atual}.json", self.colors['text_secondary']),
            ("Atualizado:", self.ultimo_timestamp or "aguardando", self.colors['text_secondary']),
        ]

        for rotulo, valor, cor in linhas:
            linha = ctk.CTkFrame(corpo, fg_color="transparent")
            linha.pack(fill="x", pady=6)
            ctk.CTkLabel(linha, text=rotulo, font=ctk.CTkFont(size=12),
                         text_color=self.colors['text_muted'], width=100,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(linha, text=valor, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=cor, anchor="e").pack(side="right")

        ctk.CTkButton(
            container,
            text="✓ ENTENDI",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.colors['accent_green'],
            hover_color="#00cc77",
            text_color="#000000",
            corner_radius=10,
            height=38,
            command=diag.destroy
        ).pack(pady=(18, 4))

    def _ajuda(self):
        ajuda = ctk.CTkToplevel(self)
        ajuda.title("Ajuda - RSI Sniper")
        ajuda.geometry("650x700")
        ajuda.configure(fg_color=self.colors['bg_primary'])

        # Container com scroll
        container = ctk.CTkScrollableFrame(
            ajuda,
            fg_color=self.colors['bg_secondary'],
            corner_radius=16
        )
        container.pack(fill="both", expand=True, padx=20, pady=20)
        self._rolar_com_mouse(ajuda, container)

        # Título
        ctk.CTkLabel(
            container,
            text="❓ GUIA DE MÉTRICAS",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.colors['accent_cyan']
        ).pack(pady=(10, 20))

        # Função auxiliar para criar seções
        def criar_secao(titulo, cor_titulo):
            frame = ctk.CTkFrame(container, fg_color=self.colors['bg_tertiary'], corner_radius=10)
            frame.pack(fill="x", pady=8, padx=10)
            ctk.CTkLabel(
                frame, text=titulo,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=cor_titulo
            ).pack(anchor="w", padx=15, pady=(12, 5))
            return frame

        def criar_item(parent, termo, descricao):
            item_frame = ctk.CTkFrame(parent, fg_color="transparent")
            item_frame.pack(fill="x", padx=15, pady=3)
            ctk.CTkLabel(
                item_frame, text=f"• {termo}:",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=self.colors['text_primary']
            ).pack(anchor="w")
            ctk.CTkLabel(
                item_frame, text=f"  {descricao}",
                font=ctk.CTkFont(size=11),
                text_color=self.colors['text_secondary'],
                wraplength=550
            ).pack(anchor="w", pady=(0, 5))

        # ═══ MONITOR ═══
        sec = criar_secao("📊 MONITOR", self.colors['accent_cyan'])
        criar_item(sec, "Status", "ATIVO = robô operando | PAUSADO = operações bloqueadas")
        criar_item(sec, "Ativo", "Símbolo do ativo sendo negociado (ex: WINM26, WDOJ26)")
        criar_item(sec, "Posições", "Quantidade de posições abertas no momento")
        criar_item(sec, "RSI", "Índice de Força Relativa (0-100). Abaixo de 30 = sobrevenda, Acima de 70 = sobrecompra")
        criar_item(sec, "Lucro do Dia", "Lucro/prejuízo realizado + flutuante do dia atual")
        criar_item(sec, "Saldo", "Saldo inicial + lucro realizado (sem lucro flutuante)")
        criar_item(sec, "Lucro Aberto", "Lucro/prejuízo das posições abertas (não realizado)")
        ctk.CTkFrame(sec, height=10, fg_color="transparent").pack()

        # ═══ AGRESSÃO ═══
        sec = criar_secao("⚡ AGRESSÃO (Fluxo de Ordens)", self.colors['accent_green'])
        criar_item(sec, "Compra %", "Percentual de ordens agressoras de compra no período")
        criar_item(sec, "Venda %", "Percentual de ordens agressoras de venda no período")
        criar_item(sec, "Volume", "Volume total de contratos no período analisado")
        criar_item(sec, "Direção", "COMPRA = fluxo comprador dominante | VENDA = fluxo vendedor | NEUTRO = equilibrado")
        criar_item(sec, "Filtro", "Quando ativado, só opera se a direção do fluxo confirmar o sinal do RSI")
        criar_item(sec, "Janela (seg)", "Quantos segundos de fluxo o robô soma antes de decidir. Menor = mais reativo")
        criar_item(sec, "Volume mín.", "Contratos mínimos na janela para o fluxo valer. Abaixo disso o filtro ignora")
        criar_item(sec, "Confirmação", "Fração de um lado para confirmar a direção. 0,70 = 70% do volume num sentido")
        ctk.CTkFrame(sec, height=10, fg_color="transparent").pack()

        # ═══ VOLUME PROFILE ═══
        sec = criar_secao("📊 VOLUME PROFILE", self.colors['accent_purple'])
        criar_item(sec, "POC", "Point of Control - preço com maior volume negociado (região de equilíbrio)")
        criar_item(sec, "VAH", "Value Area High - limite superior da área de valor (70% do volume)")
        criar_item(sec, "VAL", "Value Area Low - limite inferior da área de valor (70% do volume)")
        criar_item(sec, "Zona", "ACIMA_POC = preço acima do POC | ABAIXO_POC = preço abaixo | NA_POC = no POC")
        criar_item(sec, "Filtro", "Quando ativado, usa a zona do VP como confirmação adicional para entradas")
        criar_item(sec, "Candles", "Quantos candles entram no cálculo do perfil de volume")
        criar_item(sec, "Agrupamento", "Ticks por faixa de preço. Maior = perfil mais grosso e mais rápido de montar")
        criar_item(sec, "Zona do POC", "Pontos em torno do POC tratados como região neutra")
        ctk.CTkFrame(sec, height=10, fg_color="transparent").pack()

        # ═══ CONFIGURAÇÕES ═══
        sec = criar_secao("📉 TENDÊNCIA (Média Móvel)", self.colors['accent_yellow'])
        criar_item(sec, "Média", "Valor atual da média móvel usada como referência de tendência")
        criar_item(sec, "Mercado", "ALTA = preço acima da média | BAIXA = abaixo dela")
        criar_item(sec, "Filtro", "Quando ativado, só compra acima da média e só vende abaixo. É o filtro que mais barra sinal")
        criar_item(sec, "Método", "Como a média é calculada: Simples, Exponencial, Suavizada ou Ponderada linear")
        criar_item(sec, "Períodos", "Quantos candles entram na média. Maior = tendência mais lenta e menos sinais")
        ctk.CTkFrame(sec, height=10, fg_color="transparent").pack()

        sec = criar_secao("📏 VOLATILIDADE (ATR)", self.colors['accent_blue'])
        criar_item(sec, "Movimento", "Tamanho do movimento típico do dia, em pontos, medido pelo ATR")
        criar_item(sec, "Filtro", "Quando ativado, o stop e o alvo passam a ser calculados pela volatilidade. Stop Loss e Take Profit fixos somem das Configurações porque deixam de valer")
        criar_item(sec, "Períodos", "Quantos candles o ATR usa para medir a volatilidade")
        criar_item(sec, "Mult. stop", "Multiplica o ATR para achar a distância do stop. 1,5 = uma vez e meia o movimento normal")
        criar_item(sec, "Mult. alvo", "Multiplica o ATR para achar o alvo. Mantenha maior que o do stop")
        ctk.CTkFrame(sec, height=10, fg_color="transparent").pack()

        sec = criar_secao("⚙️ CONFIGURAÇÕES", self.colors['accent_blue'])
        criar_item(sec, "Lote", "Quantidade de contratos/lotes por operação")
        criar_item(sec, "Stop Loss", "Distância em pontos para o stop loss (proteção contra perdas)")
        criar_item(sec, "Take Profit", "Distância em pontos para o take profit (alvo de lucro)")
        criar_item(sec, "Trailing Stop", "Quando ativado, o stop se move a favor conforme o preço avança")
        criar_item(sec, "Trailing (pts)", "Distância em pontos para ativar/mover o trailing stop")
        criar_item(sec, "Períodos (RSI)", "Quantos candles o RSI olha para trás. Menor = reage mais rápido e gera mais sinais")
        criar_item(sec, "Sobrevenda", "Nível que o RSI precisa cruzar para cima para gerar compra")
        criar_item(sec, "Sobrecompra", "Nível que o RSI precisa cruzar para baixo para gerar venda")
        criar_item(sec, "Preço", "Qual preço do candle alimenta o RSI: Fechamento, Abertura, Máxima, Mínima, Mediana, Típico ou Ponderado")
        criar_item(sec, "Máx. posições", "Quantas posições o robô pode manter abertas ao mesmo tempo")
        criar_item(sec, "Salvar", "Envia todos os parâmetros ao robô, que aplica na hora, sem reiniciar")
        criar_item(sec, "Resetar", "Devolve todos os parâmetros aos valores com que o robô foi iniciado")
        ctk.CTkFrame(sec, height=10, fg_color="transparent").pack()

        # ═══ ESTRATÉGIA RSI ═══
        sec = criar_secao("📈 ESTRATÉGIA RSI SNIPER", self.colors['accent_yellow'])
        criar_item(sec, "Sinal de COMPRA", "RSI cruza acima do nível de sobrevenda (ex: 30 → 31)")
        criar_item(sec, "Sinal de VENDA", "RSI cruza abaixo do nível de sobrecompra (ex: 70 → 69)")
        criar_item(sec, "Confirmação", "Filtros de Agressão e Volume Profile refinam os sinais")
        ctk.CTkFrame(sec, height=10, fg_color="transparent").pack()

        # Botão fechar
        ctk.CTkButton(
            container,
            text="✓ ENTENDI",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.colors['accent_green'],
            hover_color="#00cc77",
            text_color="#000000",
            corner_radius=10,
            height=40,
            command=ajuda.destroy
        ).pack(pady=20)


if __name__ == "__main__":
    app = RSIPanelModern()
    app.mainloop()
