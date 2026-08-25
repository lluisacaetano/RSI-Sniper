# RSI Sniper — contexto do projeto

Robô de trading (Expert Advisor MQL5) para Mini Índice na B3, com painel de
controle em Python. Projeto MWM. **Apresentação: 19/08/2026.**

## Estado atual (24/08/2026, noite)

Painel e robô verificados campo a campo contra um EA rodando de verdade:
25 parâmetros, 7 leituras de monitoramento, liga/desliga dos 4 filtros,
RESETAR, PAUSAR/RETOMAR, FECHAR_TUDO e PARAR_EA. `teste_com_robo_vivo.py`
fecha com **PAINEL E ROBO 100% COERENTES**.

### O que mudou em 24/08 à noite

O salvamento ainda "voltava sozinho" para os valores antigos. Duas causas, as
duas com prova guardada no disco:

- **Pasta errada.** O Wine cria mais de um perfil em `drive_c/users` e cada um
  tem a sua `Common/Files`. O MetaTrader aberto pelo aplicativo roda como
  usuário Wine **`user`** (`terminal64.exe USER=user`); o `wine` chamado na
  linha de comando roda como **`luisacaetano`**. O painel escolhia a pasta uma
  vez, no `__init__`, e nunca mais revia — enquanto o canal LIVE/BACKTEST era
  redetectado a cada 250 ms. Agora `_revisar_caminho`/`_sincronizar_destino`
  acompanham os dois juntos, migram só para dado estritamente mais fresco
  (margem de 3 s) e nunca no meio de uma confirmação pendente. Todo comando
  reconfere o destino antes de gravar.
- **Confirmação falsa.** O carimbo do comando tinha precisão de segundo e o robô
  descarta carimbo que não seja mais novo que o do último lido. Dois comandos no
  mesmo segundo (um duplo-clique no SALVAR basta) tinham o mesmo texto: o
  segundo era descartado e o eco do primeiro casava com a espera do segundo — o
  painel cantava "aplicado" para um comando jogado fora. Agora cada comando leva
  **identidade única na linha 3** do arquivo, e é ela que volta no eco.

Também: `RSI_COMMON_PATH` sobrepõe a detecção (válvula de escape), o diálogo de
informações mostra a pasta em uso, e o robô ganhou **janela de validade de 5
minutos** para comandos (`VALIDADE_COMANDO_SEG`).

### O que mudou em 19/08 à tarde

- **Painel abria em branco** pelo `Abrir_Painel.app`. Causa: o `.app` executa um
  script bash, e o macOS associa o aplicativo ao PID **desse script**; o Python
  rodava como filho, então a janela nascia num processo sem rosto e nunca era
  ativada nem pintada. Corrigido com `exec "$PY" rsi_panel.py` em **todos** os
  lançadores (o `.app`, o `.command`, o `painel.sh` e os dois que o instalador
  gera). Sem `exec` o defeito volta.
- **`<TouchpadScroll>` derrubava o painel no Windows/Linux.** O evento só existe
  no Tk 9 (macOS); o Tk 8.6 levanta `TclError` só de tentar ligá-lo. Agora passa
  por `ligar_evento()`, que engole o erro. Testado em Python 3.9/Tk 8.5 e 3.14/Tk 9.
- **O `.ex5` passou a ir compilado no pacote** (`Scripts/RSI_Sniper.ex5`). Antes
  só o fonte ia, e quem não tinha o MetaEditor no lugar esperado ficava sem robô.
  A busca do MetaEditor no Windows também foi ampliada: só olhava
  `C:\Program Files\MetaTrader 5`, e corretora com pasta própria não era achada.
- **Detecção de pasta no Linux** estava mais fraca que a do macOS e Windows: sem
  fallback de `Program Files` e só olhando `~/.wine`. Agora varre também `~/.mt5`
  (instalador oficial da MetaQuotes), PlayOnLinux e Lutris.
- **Comentários do EA**: 25 de 25 funções com cabeçalho. Só comentário, nenhuma
  linha executável mudou — e o backtest de conferência reproduziu 1 442,00 com
  194 operações depois disso.
- **Documentação**: manual com seção do painel (9 páginas) e deck de 12 slides
  em `Documentacao/`. Os READMEs foram corrigidos (e os LEIA-ME de cada
  sistema viraram README.txt): mandavam compilar
  com F7 e o README da raiz listava três `.txt` que não existem.

### Linha de base do backtest — não pode mudar

Configuração `demo_2025.set`, WIN$N, H1, 02.01.2025 → 30.12.2025, OHLC 1 minuto:

| métrica | valor |
|---|---|
| Lucro Líquido Total | **1 442,00** |
| Total de Negociações | **194** |
| Fator de Lucro | 1,14 |
| Rebaixamento Máximo do Saldo | 1 280,00 (1,25%) |
| Índice de Sharpe | 2,58 |
| Qualidade do histórico | 96% |

Qualquer alteração no EA precisa reproduzir isso exatamente. Verificado três
vezes: duas depois da refatoração e uma em 19/08 13:11, com o `.ex5` recompilado
depois dos comentários novos (`conferencia_final.htm`).

## Arquitetura

Quatro arquivos em `Scripts/` (`.mq5`, `.mqh`, `.py` e agora o `.ex5`
compilado), que precisam estar sincronizados em **4 lugares**:

1. `~/dev/RSI_Sniper_Instalacao/Scripts/` (fonte)
2. `~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/` (Experts/MWM para `.mq5`, Include/MWM para `.mqh` e `.py`)
3. `~/Library/CloudStorage/GoogleDrive-lluisacaetanoaraujo@gmail.com/Meu Drive/RSI_Sniper_Instalacao/Scripts/`
4. Dentro do `RSI_Sniper_Instalacao.zip` no Drive

**Sempre conferir por hash depois de alterar** — já aconteceu de o Drive ficar
para trás e só descobrirmos quando ela perguntou.

### Como os parâmetros funcionam

Em MQL5 `input` é imutável depois que o robô inicia. Por isso todo parâmetro
vive na struct `SRSIConfig` (28 campos, em `RSIExport.mqh`), copiada dos inputs
no `OnInit`. **`cfg_original = cfg` acontece DEPOIS de todos os campos serem
preenchidos** — é o que faz o botão RESETAR restaurar tudo.

RSI, média móvel e ATR alimentam handles de indicador: mudar o período exige
recriar o handle. `RecriarIndicadoresSePreciso()` faz isso e **reverte para o
valor anterior** se o novo handle vier inválido.

Protocolo painel → robô: `SALVAR_CONFIG:chave=valor;chave=valor`. O formato
posicional antigo continua aceito. 22 parâmetros enviados, todos entendidos.
`log_nivel` e `export_ms` o robô aceita mas o painel não expõe (diagnóstico).

### Layout do painel

- **MONITOR** — lucro, saldo, lucro aberto
- **MONITORAMENTO** — 4 blocos colapsáveis: o checkbox é o título do bloco, e
  marcar expande leitura ao vivo + parâmetros daquele filtro
- **CONFIGURAÇÕES** — gestão de risco, RSI, execução, botões

A janela **mede a própria altura** (`_ajustar_altura_janela`) e **só cresce,
nunca diminui** — encolher fazia a coluna de configurações perder a última
seção. O card de Monitoramento rola por dentro quando passa do teto da tela.
Medir com `RSI_MEDIR_ALTURA=1 python3 rsi_panel.py`.

## Problema conhecido: MT5 e o backtest que não inicia

Lançar `terminal64.exe /config:...ini` **falha se o terminal ainda não
sincronizou** com a XP. O sintoma é enganoso:

```
Tester  not synchronized with trade server
Tester  WIN$N: no history data from 2025.01.02 to 2025.12.30
```

Parece falta de histórico, mas o `2025.hcc` está no disco. **Sequência que
funciona:** subir o MT5 normal → esperar a linha
`terminal synchronized with XP Investimentos ... N symbols` aparecer no
`logs/AAAAMMDD.log` → só então matar e relançar com o `/config`.

Detectar sucesso procurando `visual testing of Experts` no
`Tester/logs/AAAAMMDD.log`. Contar "linhas novas no log" dá falso positivo,
porque a mensagem de erro também é linha nova.

Em 18/08 o servidor da XP ficou ~40 min fora (`authorization failed (Service is
not available)`) e nada disso funcionava — se o loop de reautorização entre
SP2/SP3 estiver rodando sem nunca sincronizar, é a corretora, não a máquina.

### Modo visual lento

Causa medida: `LogDetalhado=2` gera log gigante (102 MB num dia, 924 MB em
outro). Usar `demo_2025_rapido.set` — idêntico ao `demo_2025.set` exceto
`LogDetalhado=1` e `IntervaloExportacao_MS=500`. Não afeta a estratégia:
mesmo 1 442,00 com 194 operações.

Configs prontos em `MetaTrader 5/config/`: `rsi_demo.ini` (visual),
`visual_rapido.ini` (visual + preset rápido), `conferencia.ini` (headless,
50 segundos, fecha o terminal ao terminar).

## Testes

Três arquivos em `Scripts/`, todos rodam com `python3 <arquivo>` e saem com
código 1 se algo falhar:

- `teste_confirmacao_painel.py` — o ciclo salvar → confirmar, com o robô
  simulado pelos mesmos dois arquivos que ele usa de verdade. 6 casos.
- `teste_roteamento_painel.py` — para onde o painel fala: dois perfis de Wine
  falsos, o robô mudando de casa, a migração, o envio que não confia na pasta
  antiga e a margem contra ruído. 9 casos.
- `teste_com_robo_vivo.py` — **exige um EA rodando**. Cobre os 25 parâmetros, o
  monitoramento, liga/desliga dos filtros e todos os botões, na ordem, deixando
  o `PARAR_EA` por último.

O jeito estável de ter robô vivo por vários minutos é o testador em modo visual
(o `[StartUp]` com EA anexado ao gráfico não serve: o gráfico é refeito quando o
terminal sincroniza e leva o EA junto):

```bash
export WINEPREFIX="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5"
export DYLD_FALLBACK_LIBRARY_PATH="/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/lib/external:/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/lib:/usr/lib"
nohup "/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine" \
  "C:\Program Files\MetaTrader 5\terminal64.exe" \
  "/config:C:\Program Files\MetaTrader 5\config\painel_vivo_tester.ini" &
# espere o rsi_data_BACKTEST.json aparecer e comecar a mudar, depois:
cd ~/DEV/RSI_Sniper_Instalacao/Scripts && python3 teste_com_robo_vivo.py
```

## Comandos úteis

```bash
# painel
cd ~/dev/RSI_Sniper_Instalacao/Scripts && python3 rsi_panel.py

# compilar o EA
export WINEPREFIX="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5"
export DYLD_FALLBACK_LIBRARY_PATH="/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/lib/external:/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/lib:/usr/lib"
cd "$WINEPREFIX/drive_c/Program Files/MetaTrader 5" && \
  "/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine" metaeditor64.exe \
  /portable "/compile:MQL5\Experts\MWM\RSI_Sniper.mq5" /log

# backtest headless de conferencia (~50s)
"/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine" \
  "C:\Program Files\MetaTrader 5\terminal64.exe" \
  "/config:C:\Program Files\MetaTrader 5\config\conferencia.ini"
```

Relatórios de backtest saem como `.htm` na raiz da pasta do MetaTrader, em
**português** no build 6090 ("Lucro Líquido Total", não "Total Net Profit").
Há 73 relatórios antigos guardados lá; 7 cobrem 2025 inteiro.

## Manual

`Documentacao/Manual_RSI_Sniper.pdf` — 9 páginas (instalar, backtest e painel),
gerado do `Manual_RSI_Sniper.html` com Chrome headless.

`Documentacao/Slides_RSI_Sniper.pdf` — deck de 12 slides, mesma receita. O HTML
tem modo de apresentação: botão **Apresentar** ou tecla `F`, setas para navegar,
`Esc` para sair. As fontes vêm do Google Fonts, então sem internet o visual muda.

Ver a memória `entregaveis-em-pdf` para o comando de conversão.

## Backups antes de mexer

- `Scripts/_backup-antes-rsi-painel/` — os 3 arquivos antes da refatoração
- `Scripts/RSI_Sniper.mq5.bak-labels-20260818` — antes dos labels novos
- `MQL5/Experts/MWM/RSI_Sniper.ex5.bak-20260818`

## Armadilhas já pagas

- **Não tirar o `exec` dos lançadores** — o painel volta a abrir em branco.
- **Não adicionar ativação por `osascript` dentro do `rsi_panel.py`.** Foi
  tentado em 19/08: bloqueia a thread do Tk no arranque e deixa a janela branca.
  Foi a causa de uma regressão que custou uma hora.
- **Ao mexer no painel, sincronizar também a cópia do Drive.** Testar só a de
  `~/DEV` esconde o problema, porque o `.app` que ela usa lê a do Drive.
- **Em subclasse de `tkinter`, `getattr(self, "x", None)` não devolve `None`.**
  O `__getattr__` do Tk repassa o atributo desconhecido para `self.tk` e estoura
  `RecursionError`. Use atributo criado no `__init__` e acesso direto.
- **Não trocar a identidade do comando por carimbo de tempo.** Precisão de
  segundo faz o eco de um comando confirmar outro.
- **Comando esquecido na `Common/Files` é mina armada.** Um `PARAR_EA` de 19/08
  ficou lá e desligaria sozinho o próximo robô a subir naquele perfil. É o que a
  janela de validade de 5 minutos resolve.
- **No testador, `ExpertRemove()` encerra o teste na hora** — o eco do `PARAR_EA`
  não chega a ser publicado. Ao vivo o EA ainda exporta antes de sair. Testar o
  `PARAR_EA` pelo silêncio do robô, não pelo eco.
- **Refazer o zip do Drive com `zip -@`** deixa de fora os PDFs com acento no
  nome (`Pré-Requisitos.pdf`, `Guia de Implantação.pdf`): o nome guardado no zip
  antigo está numa forma Unicode diferente da do disco. Conferir a contagem de
  arquivos depois (são **31**).
- **`customtkinter` não tem versão fixada** nos 9 lugares que o instalam. Hoje o
  pip entrega 6.0.0; uma 7.x incompatível quebraria o painel de todo mundo.

## Pendências

- `log_nivel` e `export_ms` não têm campo no painel (decisão, não esquecimento)
- Com os **quatro** filtros abertos ao mesmo tempo o monitoramento passa de
  1100px e o card rola; nas telas dela isso não cabe inteiro
- Subir a pasta para o Classroom só **depois** da última alteração
