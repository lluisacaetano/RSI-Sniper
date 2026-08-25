============================================================
  RSI SNIPER PRO - Scripts para Windows
============================================================

Esta pasta contém dois executáveis:


1. Instalar_RSI_Sniper.bat
------------------------------------------------------------
   O QUE FAZ:
   - Procura automaticamente a pasta do MetaTrader 5
   - Copia os arquivos do RSI Sniper para as pastas corretas
   - Cria um atalho na Area de Trabalho para abrir o painel

   QUANDO USAR:
   - Execute apenas uma vez, na primeira instalacao
   - Execute novamente se quiser atualizar os arquivos


2. Abrir_Painel.bat
------------------------------------------------------------
   O QUE FAZ:
   - Localiza o painel instalado no MetaTrader 5
   - Abre o Painel de Controle do RSI Sniper
   - Verifica e instala o CustomTkinter automaticamente
   - Se faltar o Python, o instalador avisa e indica o que baixar

   QUANDO USAR:
   - Sempre que quiser abrir o painel de controle
   - Use o atalho criado na Area de Trabalho (mais pratico)


============================================================
  ORDEM DE EXECUCAO
============================================================

   1. Execute: Instalar_RSI_Sniper.bat
   2. (o robo ja vai compilado no pacote; o F7 no MetaEditor so e
       necessario se voce alterar o RSI_Sniper.mq5)
   3. Execute: Abrir_Painel.bat (ou use o atalho no Desktop)


============================================================
  REQUISITOS
============================================================

   - Python 3.8 ou superior instalado
   - MetaTrader 5 instalado
   - CustomTkinter (instalado automaticamente)


============================================================
