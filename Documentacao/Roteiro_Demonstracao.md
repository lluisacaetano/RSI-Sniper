# Roteiro da demonstração ao vivo

Objetivo: robô rodando na tela com o painel ao lado, e a plateia mexendo nos
parâmetros. Funciona a qualquer hora — não depende do mercado estar aberto.

## Antes de começar (5 minutos, sozinho)

1. Abra o **MetaTrader 5**.
2. Espere aparecer **CONECTADO** no canto inferior direito. Sem isso o testador
   reclama de "não sincronizado" e não inicia.

## Um clique (o caminho da apresentação)

Dê dois cliques em **`Abrir_Demonstracao.command`**, na pasta do projeto.

Ele faz tudo sozinho: sobe o MetaTrader com o testador em modo visual, carrega o
preset `referencia.set`, espera o robô começar a publicar e abre o painel já
conectado. Leva cerca de um minuto. Se já houver um MetaTrader aberto, ele
pergunta antes de fechar.

Se aparecer *"O robô não começou a publicar"*, o terminal não estava conectado à
corretora — abra o MetaTrader normal, espere o **CONECTADO** no canto inferior
direito, feche e rode de novo.

Só siga os passos manuais abaixo se o lançador falhar.

## Subir o robô no testador (manual)

3. `Ctrl+R` abre o **Testador de Estratégia** na parte de baixo da tela.
   (Ou menu **Ver → Testador de estratégia**.)
4. Aba **Configuração**, preencha assim:

   | campo | valor |
   |---|---|
   | Expert Advisor (Robô) | `MWM\RSI_Sniper.ex5` |
   | Ativo | `WIN$N` · período `H1` |
   | Data | Período personalizado · `2025.01.02` → `2025.12.30` |
   | Para frente | Não |
   | Latência | Sem atrasos, execução perfeita |
   | Modelagem | **OHLC por 1 minuto** |
   | Depósito | `100000` · BRL · `1:1` |
   | Otimização | Desativada |
   | ☑ | **modo visual com exibição de gráficos, de indicadores e de negociação** |

   O último item é o que faz o gráfico aparecer. Sem ele o teste roda invisível.

5. Aba **Parâmetros de entrada** → clique com o **botão direito** na lista →
   **Carregar** → escolha **`referencia.set`**.
   É o preset dos números do slide: RSI 6, níveis 25/60, tendência desligada,
   stop 200, alvo 1200, stop móvel ligado em 100.
6. Botão verde **Iniciar** (canto inferior direito).

O gráfico abre e começa a andar. Tem um **controle de velocidade** em cima do
gráfico visual — deixe em torno de 1/3 para dar tempo de narrar.

## Abrir o painel

7. Abra o **Abrir_Painel** (o aplicativo na pasta de instalação).

O painel acha o robô sozinho: ele varre as pastas do MetaTrader, escolhe a que
tem dado mais fresco e acompanha se o robô mudar de lugar. Não importa a ordem —
pode abrir o painel antes ou depois do testador.

Confirme que o selo no topo mostra **BACKTEST** e **CONECTADO**.

## A demonstração

**Mostre primeiro que os dois conversam.** Mude um campo (o Stop Loss é o mais
visível), clique em **SALVAR** e aponte para a mensagem:

> → 25 parâmetros enviados, aguardando o robô...
> ✓ robô aplicou 25 parâmetros

O segundo aviso só aparece quando o **robô** responde, e o número vem dele. Se o
robô estivesse parado, o painel diria *"✗ o robô não leu o comando"* em vermelho
em vez de fingir sucesso.

**Depois solte a plateia.** Deixe mexerem no que quiserem:

- Marcar os filtros (Agressão, Volume Profile, Tendência, Volatilidade) abre a
  leitura ao vivo de cada um e os parâmetros daquele filtro.
- Qualquer valor fora da faixa é barrado com um aviso dizendo o campo e o limite
  aceito — e nada é enviado.
- **RESETAR devolve tudo** aos valores de partida. É a rede de segurança: pode
  deixar bagunçarem à vontade.

**Deixe o PARAR EA por último.** Ele remove o robô do gráfico *e fecha o painel*.
Se alguém clicar no meio da demonstração, acabou — precisa recomeçar do passo 3.

## Se algo der errado

| sintoma | causa | o que fazer |
|---|---|---|
| Painel abre mas diz DESCONECTADO | nenhum robô publicando | confirme que o teste está rodando (passo 6) |
| "o robô não leu o comando" | o teste terminou ou foi parado | reinicie o teste; o painel reencontra sozinho |
| Testador diz "não sincronizado" | terminal ainda conectando | espere o CONECTADO e tente de novo |
| Gráfico não aparece | o ☑ do modo visual ficou desmarcado | pare, marque, inicie de novo |
