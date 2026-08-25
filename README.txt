╔══════════════════════════════════════════════════════════════╗
║             RSI SNIPER PRO - Guia de Instalação              ║
╠══════════════════════════════════════════════════════════════╣
║  Robô de trading baseado em RSI com painel de controle       ║
║  Compatível: Windows, macOS (Wine) e Linux (Wine)            ║
╚══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONTEUDO DO PACOTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Scripts/ (Arquivos do Robo)
     - RSI_Sniper.ex5    - Expert Advisor ja compilado (e o que roda)
     - RSI_Sniper.mq5    - codigo fonte do Expert Advisor
     - RSIExport.mqh     - Biblioteca de comunicação
     - rsi_panel.py      - Painel de controle Python

  Instalacao/ (Scripts por Sistema Operacional)
     - Windows/
        - Instalar_RSI_Sniper.bat - Instala os arquivos
        - Abrir_Painel.bat        - Abre o painel
        - README.txt              - Instrucoes

     - macOS/
        - Instalar_RSI_Sniper.app - Instala os arquivos
        - Abrir_Painel.app        - Abre o painel
        - README.txt              - Instrucoes

     - Linux/
        - instalar.sh             - Instala os arquivos
        - painel.sh               - Abre o painel
        - README.txt              - Instrucoes

     - install_rsi_sniper.py      - Instalador via terminal

  Documentacao/
     - Manual_RSI_Sniper.pdf      - Instalar, rodar o backtest e usar o painel
     - Slides_RSI_Sniper.pdf      - Apresentacao do projeto
     - Manual de Funcionamento.pdf
     - Pre-Requisitos.pdf
     - Guia de Implantação.pdf

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  INSTALACAO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  macOS:
  ─────────
  1. Abra a pasta "Instalacao/macOS"
  2. De duplo clique em "Instalar_RSI_Sniper.app"
  3. Siga as instrucoes no Terminal

  Windows:
  ───────────
  1. Abra a pasta "Instalacao/Windows"
  2. De duplo clique em "Instalar_RSI_Sniper.bat"
  3. Siga as instrucoes

  Linux:
  ─────────
  1. Abra a pasta "Instalacao/Linux"
  2. Execute: ./instalar.sh (ou duplo clique)
  3. Siga as instrucoes

  O robo ja vai compilado no pacote nos tres sistemas. O F7 no
  MetaEditor so e necessario se voce alterar o RSI_Sniper.mq5.

  Via Terminal (qualquer SO):
  ──────────────────────────────
  cd Instalacao
  python3 install_rsi_sniper.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  USANDO O PAINEL DE CONTROLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  macOS:     Abra Instalacao/macOS/Abrir_Painel.app
  Windows:   Abra Instalacao/Windows/Abrir_Painel.bat
  Linux:     Execute Instalacao/Linux/painel.sh

  Apos a instalacao, use o atalho criado na Area de Trabalho.

  O painel instala dependencias automaticamente na primeira execucao.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONFIGURACAO NO METATRADER 5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Abra o MetaTrader 5
  2. Va em: Ferramentas > Opcoes > Expert Advisors
  3. Marque:
     [x] Permitir trading algoritmico
     [x] Permitir importacao de DLL
  4. No Navegador, expanda: Expert Advisors > MWM
  5. Arraste "RSI_Sniper" para o grafico desejado
  6. Configure os parametros e clique OK

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ONDE OS ARQUIVOS SAO INSTALADOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  MQL5/
  |── Experts/
  |   └── MWM/
  |       |── RSI_Sniper.ex5      <- Expert Advisor compilado (e o que roda)
  |       └── RSI_Sniper.mq5      <- codigo fonte
  └── Include/
      └── MWM/
          |── RSIExport.mqh       <- Biblioteca
          └── rsi_panel.py        <- Painel Python

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CARACTERISTICAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  - Painel de controle moderno com tema escuro
  - Sistema de trailing stop configuravel
  - Quatro filtros de confirmacao (Agressao, Volume Profile,
    Tendencia e Volatilidade/ATR), cada um com direito de veto
  - Logs em tempo real
  - Configuracao dinamica sem recompilar
  - Funciona em LIVE e BACKTEST
  - Instalacao automatica multiplataforma
  - Dependencias instaladas automaticamente

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SUPORTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Em caso de duvidas ou problemas, verifique:
  - Python 3.8+ esta instalado (python3 --version)
  - MetaTrader 5 esta instalado corretamente
  - O RSI_Sniper.ex5 esta em MQL5/Experts/MWM (vai pronto no pacote)
  - Leia o arquivo README.txt na pasta do seu sistema

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Versao: 1.1 | Projeto MWM | Agosto 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
