//+------------------------------------------------------------------+
//|                         RSI SNIPER                               |
//|                                                                  |
//| Robô de trading baseado em RSI com filtros opcionais:            |
//| - Agressão (fluxo de ordens): confirma sinais com pressão real   |
//| - Volume Profile (POC/VAH/VAL): identifica zonas de valor        |
//|                                                                  |
//| Funciona em modo LIVE e BACKTEST (Strategy Tester)               |
//| Exporta dados para painel Python externo (rsi_panel.py)          |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026"
#property version   "1.00"

#include <Trade/Trade.mqh>
#include <MWM/RSIExport.mqh>

//+------------------------------------------------------------------+
//| ESTRUTURAS DE DADOS                                              |
//+------------------------------------------------------------------+

// Dados de Agressao (Fluxo de Ordens)
struct AgressaoData {
   bool     ok;
   int      nTicks;
   int      janelaSeg;
   double   volumeTotal;
   double   volumeCompra;
   double   volumeVenda;
   double   pctCompra;       // 0..1
   double   pctVenda;        // 0..1
   string   direcao;         // "COMPRA", "VENDA" ou "NEUTRO"
};

// Dados de Volume Profile
struct VolumeProfileData {
   bool     ok;
   double   poc;             // Point of Control
   double   pocVolume;
   double   vah;             // Value Area High
   double   val;             // Value Area Low
   double   precoAtual;
   string   zona;            // "ACIMA_POC", "ABAIXO_POC", "NO_POC"
};

//+------------------------------------------------------------------+
//| SISTEMA DE LOG PERSONALIZADO                                     |
//+------------------------------------------------------------------+

enum ENUM_LOG_LEVEL {
   LOG_NONE = 0,      // Sem logs
   LOG_ERROR = 1,     // Apenas erros críticos
   LOG_INFO = 2,      // Informações importantes (sinais, execuções)
   LOG_DEBUG = 3      // Detalhes técnicos completos
};

int log_file_handle = INVALID_HANDLE;

// Buffer circular de logs para o painel (últimas 50 mensagens)
string g_log_buffer[];
int g_log_count = 0;
int g_log_index = 0;  // Índice circular para inserção
int LOG_BUFFER_SIZE = 50;
bool g_log_buffer_initialized = false;

//+------------------------------------------------------------------+
//| Função de log personalizado - grava em arquivo separado          |
//+------------------------------------------------------------------+
void LogMsg(ENUM_LOG_LEVEL level, string message) {
   // Verifica se deve logar baseado no nível configurado
   if(level > cfg.log_nivel)
      return;

   // Nome do nível
   string level_str = "";
   switch(level) {
      case LOG_ERROR: level_str = "ERROR"; break;
      case LOG_INFO:  level_str = "INFO "; break;
      case LOG_DEBUG: level_str = "DEBUG"; break;
      default: return;
   }

   // Formato: [YYYY.MM.DD HH:MM:SS] [LEVEL] Mensagem
   datetime now = TimeLocal();
   string timestamp = TimeToString(now, TIME_DATE|TIME_SECONDS);
   string log_line = StringFormat("[%s] [%s] %s\n", timestamp, level_str, message);

   // Grava no arquivo (append mode para manter histórico)
   if(log_file_handle == INVALID_HANDLE) {
      string filename = StringFormat("RSI_Sniper_%s.log", _Symbol);
      // FILE_READ|FILE_WRITE permite append sem truncar
      log_file_handle = FileOpen(filename, FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
      if(log_file_handle == INVALID_HANDLE) {
         // Se não existe, cria novo
         log_file_handle = FileOpen(filename, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
      }
   }

   if(log_file_handle != INVALID_HANDLE) {
      FileSeek(log_file_handle, 0, SEEK_END);
      FileWriteString(log_file_handle, log_line);
      FileFlush(log_file_handle);
   }

   // Verifica se é linha de separação (não adiciona prefixo)
   bool is_separator = (StringFind(message, "----") == 0 || StringFind(message, "====") == 0);

   // Imprime no terminal com prefixo visual (exceto separadores)
   if(is_separator)
      Print(message);
   else if(level == LOG_ERROR)
      Print("[ERRO] ", message);
   else if(level == LOG_INFO)
      Print("[OK] ", message);
   else if(level == LOG_DEBUG)
      Print("[DBG] ", message);

   // Adiciona ao buffer circular para o painel (apenas INFO e ERROR)
   if(level <= LOG_INFO) {
      // Pré-aloca buffer na primeira vez (O(1) depois)
      if(!g_log_buffer_initialized) {
         ArrayResize(g_log_buffer, LOG_BUFFER_SIZE);
         for(int i = 0; i < LOG_BUFFER_SIZE; i++)
            g_log_buffer[i] = "";
         g_log_buffer_initialized = true;
      }

      // Adiciona prefixo e mensagem no índice atual (sem prefixo para separadores)
      string prefix = is_separator ? "" : ((level == LOG_ERROR) ? "[ERRO] " : "[OK] ");
      g_log_buffer[g_log_index] = prefix + message;

      // Avança índice circular
      g_log_index = (g_log_index + 1) % LOG_BUFFER_SIZE;
      if(g_log_count < LOG_BUFFER_SIZE)
         g_log_count++;
   }
}

//+------------------------------------------------------------------+
//| PARAMETROS DE ENTRADA                                            |
//+------------------------------------------------------------------+

input group "RSI (Índice de Força Relativa)"
input int RSI_Period = 14;                        // Períodos do RSI (candles usados no cálculo)
input ENUM_APPLIED_PRICE RSI_Price = PRICE_CLOSE; // Preço do candle usado no cálculo do RSI
input double RSI_Oversold = 40.0;                 // Nível de sobrevenda: cruzar para cima gera compra
input double RSI_Overbought = 60.0;               // Nível de sobrecompra: cruzar para baixo gera venda

input group "Filtro de Agressão (fluxo de ordens)"
input bool UsarAgressao = false;                  // Ativar filtro de agressão (exige fluxo em tempo real)
input int Agressao_JanelaSeg = 1;                 // Janela de leitura do fluxo (segundos)
input double Agressao_VolumeMinimo = 500;         // Volume mínimo na janela para o fluxo valer (contratos)
input double Agressao_PctMinimo = 0.70;           // Percentual de um lado para confirmar a direção (0,70 = 70%)

input group "Filtro de Volume Profile (POC)"
input bool UsarVolumeProfile = false;             // Ativar filtro de Volume Profile
input int VP_Barras = 60;                         // Candles usados para montar o perfil de volume
input int VP_PassoTicks = 5;                      // Agrupamento do perfil (ticks por faixa de preço)
input double VP_MargemPOC = 10;                   // Zona neutra em torno do POC (pontos)

input group "Filtro de Tendência (média móvel)"
input bool UsarFiltroTendencia = false;           // Ativar filtro de tendência (só compra acima da média)
input int MM_Periodo = 50;                        // Períodos da média móvel de tendência
input ENUM_MA_METHOD MM_Metodo = MODE_EMA;        // Método de cálculo da média móvel

input group "Stop e Alvo por Volatilidade (ATR)"
input bool UsarATR = false;                       // Calcular stop e alvo pela volatilidade, não por pontos fixos
input int ATR_Periodo = 14;                       // Períodos do ATR
input double ATR_Mult_SL = 1.5;                   // Multiplicador do ATR para o stop loss
input double ATR_Mult_TP = 3.0;                   // Multiplicador do ATR para o take profit

input group "Gerenciamento de Risco"
input double LotSize = 1.0;                       // Volume por operação (contratos)
input double TakeProfit_Points = 350;             // Take profit: alvo de ganho (pontos)
input double StopLoss_Points = 200;               // Stop loss: perda máxima por operação (pontos)
input bool UseTrailingStop = true;                // Ativar stop móvel (acompanha o preço a favor)
input double TrailingStop_Points = 150;           // Distância do stop móvel até o preço (pontos)

input group "Controle de Execução"
input int MaxPositions = 1;                       // Máximo de posições abertas ao mesmo tempo
input ulong MagicNumber = 123456;                 // Número que identifica as ordens deste robô
input ENUM_LOG_LEVEL LogDetalhado = LOG_INFO;     // Nível de detalhe do diário de execução

input group "Painel Externo"
input bool UsarPainelExterno = true;              // Exportar dados para o painel de controle
input uint IntervaloExportacao_MS = 500;          // Intervalo entre exportações para o painel (ms)

//+------------------------------------------------------------------+
//| VARIAVEIS GLOBAIS                                                |
//+------------------------------------------------------------------+

// Parametros com que cada indicador foi criado, para saber quando recriar
int  ind_rsi_period = -1, ind_rsi_price = -1;
int  ind_mm_periodo = -1, ind_mm_metodo = -1;
int  ind_atr_periodo = -1;


CTrade trade;
int rsi_handle;
double rsi_buffer[];
int mm_handle  = INVALID_HANDLE;   // media movel do filtro de tendencia
int atr_handle = INVALID_HANDLE;   // ATR do stop por volatilidade
double mm_buffer[];
double atr_buffer[];
double g_mm_valor  = 0;            // ultimos valores lidos, tambem exportados ao painel
double g_atr_valor = 0;
string g_tendencia = "";           // "ALTA", "BAIXA" ou "" quando o filtro esta desligado
bool buy_signal_sent = false;
bool sell_signal_sent = false;
bool aguardando_entrada = false;  // Bloqueia novas entradas enquanto ordem está pendente
datetime aguardando_desde = 0;    // Quando a trava acima foi ligada
#define AGUARDA_ENTRADA_SEG 10    // Tempo maximo que a trava pode ficar ligada
// Configuracoes do EA (usando struct do RSIExport)
SRSIConfig cfg;           // Configuracoes atuais (modificaveis pelo painel)
SRSIConfig cfg_original;  // Configuracoes originais (para resetar)

double lucro_dia = 0.0;
double lucro_realizado = 0.0;  // Lucro de trades fechados (do dia)
double lucro_total_backtest = 0.0;  // Lucro total acumulado (todo o backtest)
double saldo_inicial = 0.0;    // Saldo no início do backtest

CRSIExport* exportador = NULL;
uint ultima_exportacao = 0;  // GetTickCount() retorna uint, não datetime
uint ultima_atualizacao_lucro = 0;  // Throttle para AtualizarLucroDia

double vol_min, vol_max, vol_step;

AgressaoData g_agressao;
VolumeProfileData g_volumeProfile;
datetime g_lastCalcSec = 0;

//+------------------------------------------------------------------+
//| Converte volume do tick para double                              |
//+------------------------------------------------------------------+
double TickVolumeToDouble(const MqlTick &t) {
   double vr = (double)t.volume_real;
   if(vr > 0.0) return vr;
   return (double)t.volume;
}

//+------------------------------------------------------------------+
//| Calcula agressao (fluxo de ordens) na janela de tempo            |
//+------------------------------------------------------------------+
AgressaoData CalcularAgressao() {
   AgressaoData a;
   a.ok = false;
   a.nTicks = 0;
   a.janelaSeg = cfg.agr_janela;
   a.volumeTotal = 0.0;
   a.volumeCompra = 0.0;
   a.volumeVenda = 0.0;
   a.pctCompra = 0.0;
   a.pctVenda = 0.0;
   a.direcao = "NEUTRO";

   datetime t2 = TimeTradeServer();
   datetime t1 = t2 - (datetime)cfg.agr_janela;
   if(t1 <= 0) t1 = t2 - 1;

   MqlTick ticks[];
   int copied = CopyTicksRange(_Symbol, ticks, COPY_TICKS_TRADE,
                               (ulong)t1 * 1000, (ulong)t2 * 1000);
   if(copied <= 0)
      return a;

   double buyVol = 0.0;
   double sellVol = 0.0;
   double total = 0.0;

   for(int i = 0; i < copied; i++) {
      double v = TickVolumeToDouble(ticks[i]);
      if(v <= 0.0) continue;

      total += v;

      bool isBuy = ((ticks[i].flags & TICK_FLAG_BUY) != 0);
      bool isSell = ((ticks[i].flags & TICK_FLAG_SELL) != 0);

      if(isBuy && !isSell) {
         buyVol += v;
      }
      else if(isSell && !isBuy) {
         sellVol += v;
      }
      else {
         // Fallback: compara LAST com BID/ASK
         double last = ticks[i].last;
         double bid = ticks[i].bid;
         double ask = ticks[i].ask;

         if(ask > 0 && last >= (ask - _Point * 0.5))
            buyVol += v;
         else if(bid > 0 && last <= (bid + _Point * 0.5))
            sellVol += v;
      }
   }

   if(total <= 0.0)
      return a;

   a.ok = true;
   a.nTicks = copied;
   a.volumeTotal = total;
   a.volumeCompra = buyVol;
   a.volumeVenda = sellVol;
   a.pctCompra = buyVol / total;
   a.pctVenda = sellVol / total;

   if(a.pctCompra >= cfg.agr_pctmin && a.volumeTotal >= cfg.agr_volmin)
      a.direcao = "COMPRA";
   else if(a.pctVenda >= cfg.agr_pctmin && a.volumeTotal >= cfg.agr_volmin)
      a.direcao = "VENDA";
   else
      a.direcao = "NEUTRO";

   return a;
}

//+------------------------------------------------------------------+
//| Funcoes auxiliares do Volume Profile                             |
//+------------------------------------------------------------------+
double PriceStep() {
   return _Point * (double)MathMax(1, cfg.vp_passo);
}

// Converte preco <-> indice de faixa do perfil. O Volume Profile agrupa os
// ticks em faixas de largura step (cfg.vp_passo), e indexa o array direto por
// esse numero, o que da acesso O(1) em vez de varrer o perfil a cada tick.
long PriceToIndex(double price, double step) {
   return (long)MathRound(price / step);
}

// Volta do indice da faixa para o preco no centro dela.
double IndexToPrice(long idx, double step) {
   return (double)idx * step;
}

//+------------------------------------------------------------------+
//| Calcula Volume Profile (POC, VAH, VAL) - OTIMIZADO O(n)          |
//+------------------------------------------------------------------+
VolumeProfileData CalcularVolumeProfile() {
   VolumeProfileData vp;
   vp.ok = false;
   vp.poc = 0.0;
   vp.pocVolume = 0.0;
   vp.vah = 0.0;
   vp.val = 0.0;
   vp.precoAtual = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   vp.zona = "INDEFINIDO";

   MqlRates rates[];
   int cnt = CopyRates(_Symbol, PERIOD_M1, 0, cfg.vp_barras, rates);
   if(cnt <= 0)
      return vp;

   ArraySetAsSeries(rates, false);

   double step = PriceStep();

   // Primeiro passo: encontrar range global de preços
   double globalLow = rates[0].low;
   double globalHigh = rates[0].high;
   for(int i = 1; i < cnt; i++) {
      if(rates[i].low < globalLow) globalLow = rates[i].low;
      if(rates[i].high > globalHigh) globalHigh = rates[i].high;
   }

   long idxMin = PriceToIndex(globalLow, step);
   long idxMax = PriceToIndex(globalHigh, step);
   int niveis = (int)(idxMax - idxMin + 1);

   if(niveis <= 0 || niveis > 10000)  // Limite de segurança
      return vp;

   // Aloca array de volumes com indexação direta (O(1) acesso)
   double volumes[];
   ArrayResize(volumes, niveis);
   ArrayInitialize(volumes, 0.0);

   // Segundo passo: acumular volumes (O(n) total)
   for(int i = 0; i < cnt; i++) {
      long i_lo = PriceToIndex(rates[i].low, step) - idxMin;
      long i_hi = PriceToIndex(rates[i].high, step) - idxMin;
      if(i_hi < i_lo) { long t = i_hi; i_hi = i_lo; i_lo = t; }

      int slots = (int)(i_hi - i_lo + 1);
      if(slots <= 0) slots = 1;
      double vshare = (double)rates[i].tick_volume / (double)slots;

      for(long k = i_lo; k <= i_hi && k < niveis; k++) {
         volumes[(int)k] += vshare;
      }
   }

   // Terceiro passo: encontrar POC e calcular total
   int pocIdx = 0;
   double maxVol = 0.0;
   double totalVol = 0.0;
   for(int i = 0; i < niveis; i++) {
      totalVol += volumes[i];
      if(volumes[i] > maxVol) {
         maxVol = volumes[i];
         pocIdx = i;
      }
   }

   if(totalVol <= 0)
      return vp;

   vp.ok = true;
   vp.poc = IndexToPrice(idxMin + pocIdx, step);
   vp.pocVolume = maxVol;

   // Value Area (70% do volume) - usando indexação direta
   double targetVol = totalVol * 0.70;
   double coveredVol = maxVol;

   int valIdx = pocIdx;
   int vahIdx = pocIdx;

   while(coveredVol < targetVol) {
      double volBelow = (valIdx > 0) ? volumes[valIdx - 1] : 0;
      double volAbove = (vahIdx < niveis - 1) ? volumes[vahIdx + 1] : 0;

      if(volBelow <= 0 && volAbove <= 0) break;

      if(volBelow >= volAbove && volBelow > 0) {
         valIdx--;
         coveredVol += volBelow;
      } else if(volAbove > 0) {
         vahIdx++;
         coveredVol += volAbove;
      } else break;
   }

   vp.val = IndexToPrice(idxMin + valIdx, step);
   vp.vah = IndexToPrice(idxMin + vahIdx, step);

   double margem = cfg.vp_margem * _Point;
   if(vp.precoAtual >= vp.poc - margem && vp.precoAtual <= vp.poc + margem)
      vp.zona = "NO_POC";
   else if(vp.precoAtual > vp.poc)
      vp.zona = "ACIMA_POC";
   else
      vp.zona = "ABAIXO_POC";

   return vp;
}

//+------------------------------------------------------------------+
//| Ajusta SL/TP para respeitar STOPS_LEVEL do simbolo               |
//+------------------------------------------------------------------+
void AjustarStops(double preco_entrada, double &sl, double &tp, bool is_buy) {
   long stops_level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   long spread_points = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   double spread = (double)spread_points * point;
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   // Margem de seguranca adicional (em pontos)
   long margem_seguranca = 15;

   // Calcula distancia minima respeitando SYMBOL_TRADE_STOPS_LEVEL
   long dist_minima_pontos = stops_level + margem_seguranca;

   // Se stops_level for 0, usa margem maior para seguranca
   if(stops_level == 0)
      dist_minima_pontos = margem_seguranca + 10;

   // Calcula distancia em preco
   double dist_minima = dist_minima_pontos * point;

   // Garante que seja pelo menos 3x o spread
   double spread_minimo = spread * 3;
   if(dist_minima < spread_minimo)
      dist_minima = spread_minimo;

   if(cfg.log_nivel >= LOG_DEBUG) {
      Print("  [DEBUG] Ajuste de Stops:");
      Print("    SYMBOL_TRADE_STOPS_LEVEL: ", stops_level, " pontos");
      Print("    Margem de seguranca: ", margem_seguranca, " pontos");
      Print("    Distancia minima total: ", dist_minima_pontos, " pontos");
      Print("    Spread: ", spread_points, " pontos");
   }

   // Armazena valores originais para comparacao
   double sl_original = sl;
   double tp_original = tp;

   if(is_buy) {
      // COMPRA: SL abaixo do preco, TP acima
      double dist_sl_atual = preco_entrada - sl;
      double dist_tp_atual = tp - preco_entrada;

      if(dist_sl_atual < dist_minima)
         sl = preco_entrada - dist_minima;
      if(dist_tp_atual < dist_minima)
         tp = preco_entrada + dist_minima;
   } else {
      // VENDA: SL acima do preco, TP abaixo
      double dist_sl_atual = sl - preco_entrada;
      double dist_tp_atual = preco_entrada - tp;

      if(dist_sl_atual < dist_minima)
         sl = preco_entrada + dist_minima;
      if(dist_tp_atual < dist_minima)
         tp = preco_entrada - dist_minima;
   }

   // CRÍTICO: Normaliza para tick size ANTES da validação final
   if(tick_size > 0) {
      sl = MathRound(sl / tick_size) * tick_size;
      tp = MathRound(tp / tick_size) * tick_size;
   }

   // VALIDAÇÃO FINAL: Após o arredondamento, garante que a distância ainda é válida
   double dist_sl_apos_arred = is_buy ? (preco_entrada - sl) : (sl - preco_entrada);
   double dist_tp_apos_arred = is_buy ? (tp - preco_entrada) : (preco_entrada - tp);

   // Se o arredondamento reduziu abaixo do mínimo, adiciona mais um tick
   if(dist_sl_apos_arred < dist_minima) {
      if(is_buy)
         sl -= tick_size;
      else
         sl += tick_size;
   }

   if(dist_tp_apos_arred < dist_minima) {
      if(is_buy)
         tp += tick_size;
      else
         tp -= tick_size;
   }

   // Recalcula distancias finais
   double dist_sl_final = is_buy ? (preco_entrada - sl) : (sl - preco_entrada);
   double dist_tp_final = is_buy ? (tp - preco_entrada) : (preco_entrada - tp);

   if(cfg.log_nivel >= LOG_DEBUG) {
      Print("    SL original: ", DoubleToString(sl_original, _Digits),
            " -> Final: ", DoubleToString(sl, _Digits),
            " (distancia: ", (int)(dist_sl_final / point), " pts)");
      Print("    TP original: ", DoubleToString(tp_original, _Digits),
            " -> Final: ", DoubleToString(tp, _Digits),
            " (distancia: ", (int)(dist_tp_final / point), " pts)");

      if(sl != sl_original || tp != tp_original) {
         Print("    >>> STOPS AJUSTADOS PARA RESPEITAR DISTANCIA MINIMA");
      }
   }
}

//+------------------------------------------------------------------+
//| Normaliza volume de acordo com regras do simbolo                 |
//+------------------------------------------------------------------+
double NormalizarVolume(double volume) {
   // vol_min, vol_max, vol_step já são globais inicializadas no OnInit()
   double minimo_efetivo = vol_min;
   if(vol_step > vol_min && vol_step > 0)
      minimo_efetivo = vol_step;

   if(volume < minimo_efetivo)
      volume = minimo_efetivo;

   if(vol_step > 0) {
      volume = MathRound(volume / vol_step) * vol_step;
      if(volume <= 0)
         volume = minimo_efetivo;
   }

   if(volume > vol_max)
      volume = vol_max;

   return NormalizeDouble(volume, 2);
}

//+------------------------------------------------------------------+
//| Verifica confirmacao para COMPRA                                 |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Le a media movel e diz de que lado dela o preco esta              |
//| Retorna "ALTA", "BAIXA" ou "" se o filtro estiver desligado       |
//+------------------------------------------------------------------+
string LerTendencia() {
   if(!cfg.usar_tendencia || mm_handle == INVALID_HANDLE)
      return "";

   if(CopyBuffer(mm_handle, 0, 0, 1, mm_buffer) <= 0)
      return "";  // ainda sem dado suficiente: nao bloqueia nem confirma

   g_mm_valor = mm_buffer[0];
   double preco = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(preco <= 0 || g_mm_valor <= 0)
      return "";

   return (preco > g_mm_valor) ? "ALTA" : "BAIXA";
}

//+------------------------------------------------------------------+
//| Le o ATR (tamanho do movimento normal) em pontos                  |
//| Retorna 0 quando o ATR esta desligado ou ainda sem dado           |
//+------------------------------------------------------------------+
double LerATRPontos() {
   if(!cfg.usar_atr || atr_handle == INVALID_HANDLE)
      return 0;

   if(CopyBuffer(atr_handle, 0, 0, 1, atr_buffer) <= 0)
      return 0;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0)
      return 0;

   g_atr_valor = atr_buffer[0] / point;   // guarda em pontos, como o resto do EA
   return g_atr_valor;
}

//+------------------------------------------------------------------+
//| Stop e alvo do momento: fixos, ou proporcionais ao ATR            |
//+------------------------------------------------------------------+
void DistanciasAtuais(double &sl_pts, double &tp_pts) {
   sl_pts = cfg.sl;
   tp_pts = cfg.tp;

   double atr = LerATRPontos();
   if(atr <= 0)
      return;   // ATR desligado ou sem dado: mantem os pontos fixos

   sl_pts = atr * cfg.atr_mult_sl;
   tp_pts = atr * cfg.atr_mult_tp;

   // Piso de seguranca: um ATR minusculo geraria stop colado no preco
   double minimo = 50;
   if(sl_pts < minimo) sl_pts = minimo;
   if(tp_pts < minimo * 2) tp_pts = minimo * 2;
}

//+------------------------------------------------------------------+
//| Ultima palavra antes de comprar: o RSI ja deu o sinal, aqui os   |
//| filtros ligados tem direito de veto. Basta um barrar para negar. |
//| Filtro desligado nao opina. Ver ConfirmacaoVenda para o espelho. |
//+------------------------------------------------------------------+
bool ConfirmacaoCompra() {
   bool confirmado = true;

   // Filtro de tendencia: o RSI aponta reversao, mas comprar numa queda firme
   // e comprar na faca. So entra quando a mare ja esta a favor.
   if(cfg.usar_tendencia) {
      string tend = LerTendencia();
      if(tend == "BAIXA") {
         if(cfg.log_nivel >= LOG_DEBUG)
            Print("    Tendencia: preco ABAIXO da media - compra rejeitada");
         return false;
      }
   }

   if(cfg.usar_agressao) {
      if(g_agressao.ok) {
         if(g_agressao.direcao == "COMPRA") {
            if(cfg.log_nivel >= LOG_DEBUG)
               Print("    Agressao: COMPRADORES dominando (",
                     DoubleToString(g_agressao.pctCompra * 100, 1), "%)");
         } else {
            if(cfg.log_nivel >= LOG_DEBUG)
               Print("    Agressao: ", g_agressao.direcao,
                     " (Compra: ", DoubleToString(g_agressao.pctCompra * 100, 1), "%)");
            confirmado = false;
         }
      }
   }

   if(cfg.usar_volume_profile && confirmado) {
      if(g_volumeProfile.ok) {
         // Nao compra o que ja esta caro: se o preco esta acima do POC, ele
         // ja subiu alem da regiao onde o mercado concentrou o volume.
         if(g_volumeProfile.zona == "ACIMA_POC") {
            if(cfg.log_nivel >= LOG_DEBUG)
               Print("    Volume Profile: preco ACIMA do POC (",
                     DoubleToString(g_volumeProfile.poc, _Digits), ") - compra rejeitada");
            confirmado = false;
         } else {
            if(cfg.log_nivel >= LOG_DEBUG)
               Print("    Volume Profile: Preco ", g_volumeProfile.zona,
                     " | POC: ", DoubleToString(g_volumeProfile.poc, _Digits));
         }
      }
   }

   return confirmado;
}

//+------------------------------------------------------------------+
//| Verifica confirmacao para VENDA                                  |
//+------------------------------------------------------------------+
bool ConfirmacaoVenda() {
   bool confirmado = true;

   // Espelho da compra: nao vende contra uma alta firme.
   if(cfg.usar_tendencia) {
      string tend = LerTendencia();
      if(tend == "ALTA") {
         if(cfg.log_nivel >= LOG_DEBUG)
            Print("    Tendencia: preco ACIMA da media - venda rejeitada");
         return false;
      }
   }

   if(cfg.usar_agressao) {
      if(g_agressao.ok) {
         if(g_agressao.direcao == "VENDA") {
            if(cfg.log_nivel >= LOG_DEBUG)
               Print("    Agressao: VENDEDORES dominando (",
                     DoubleToString(g_agressao.pctVenda * 100, 1), "%)");
         } else {
            if(cfg.log_nivel >= LOG_DEBUG)
               Print("    Agressao: ", g_agressao.direcao,
                     " (Venda: ", DoubleToString(g_agressao.pctVenda * 100, 1), "%)");
            confirmado = false;
         }
      }
   }

   if(cfg.usar_volume_profile && confirmado) {
      if(g_volumeProfile.ok) {
         // Espelho da compra: nao vende o que ja esta barato, abaixo da
         // regiao onde o mercado concentrou o volume.
         if(g_volumeProfile.zona == "ABAIXO_POC") {
            if(cfg.log_nivel >= LOG_DEBUG)
               Print("    Volume Profile: preco ABAIXO do POC (",
                     DoubleToString(g_volumeProfile.poc, _Digits), ") - venda rejeitada");
            confirmado = false;
         } else {
            if(cfg.log_nivel >= LOG_DEBUG)
               Print("    Volume Profile: Preco ", g_volumeProfile.zona,
                     " | POC: ", DoubleToString(g_volumeProfile.poc, _Digits));
         }
      }
   }

   return confirmado;
}

//+------------------------------------------------------------------+
//| Inicializacao                                                    |
//+------------------------------------------------------------------+
int OnInit() {
   LogMsg(LOG_INFO, "============================================================");
   LogMsg(LOG_INFO, "RSI SNIPER - Inicializando");
   LogMsg(LOG_INFO, "============================================================");

   vol_min = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   vol_max = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   vol_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   LogMsg(LOG_INFO, StringFormat("Ativo: %s | Timeframe: %s", _Symbol, EnumToString(_Period)));

   // Inicializa struct de configuracoes
   cfg.pausado = false;
   cfg.lote = NormalizarVolume(LotSize);
   if(cfg.lote != LotSize)
      LogMsg(LOG_INFO, StringFormat("Lote ajustado: %.2f -> %.2f", LotSize, cfg.lote));

   cfg.sl = StopLoss_Points;
   cfg.tp = TakeProfit_Points;
   cfg.trailing = UseTrailingStop;
   cfg.trailing_pts = TrailingStop_Points;
   cfg.usar_agressao = UsarAgressao;
   cfg.usar_volume_profile = UsarVolumeProfile;
   cfg.usar_tendencia = UsarFiltroTendencia;
   cfg.usar_atr = UsarATR;

   // A partir daqui todo parametro vive na struct: o painel altera em tempo real
   cfg.rsi_period  = RSI_Period;             cfg.rsi_price   = (int)RSI_Price;
   cfg.rsi_os      = RSI_Oversold;           cfg.rsi_ob      = RSI_Overbought;
   cfg.agr_janela  = Agressao_JanelaSeg;
   cfg.agr_volmin  = Agressao_VolumeMinimo;  cfg.agr_pctmin  = Agressao_PctMinimo;
   cfg.vp_barras   = VP_Barras;              cfg.vp_passo    = VP_PassoTicks;
   cfg.vp_margem   = VP_MargemPOC;
   cfg.mm_periodo  = MM_Periodo;             cfg.mm_metodo   = (int)MM_Metodo;
   cfg.atr_periodo = ATR_Periodo;
   cfg.atr_mult_sl = ATR_Mult_SL;            cfg.atr_mult_tp = ATR_Mult_TP;
   cfg.max_pos     = MaxPositions;
   cfg.log_nivel   = (int)LogDetalhado;
   cfg.export_ms   = (int)IntervaloExportacao_MS;

   // Fotografia dos valores de partida, que o botao RESETAR do painel devolve.
   // TEM que ficar DEPOIS de todos os 28 campos de cfg serem preenchidos: subir
   // esta linha faz o RESETAR restaurar campos pela metade, e o robo passa a
   // operar com uma configuracao que nunca foi pedida. Ao acrescentar campo
   // novo em SRSIConfig, preencha-o ACIMA daqui.
   cfg_original = cfg;

   // Guarda saldo inicial para calcular lucro realizado no backtest
   // (ACCOUNT_BALANCE não atualiza em tempo real no Strategy Tester)
   saldo_inicial = AccountInfoDouble(ACCOUNT_BALANCE);
   lucro_realizado = 0.0;

   rsi_handle = iRSI(_Symbol, _Period, cfg.rsi_period, (ENUM_APPLIED_PRICE)cfg.rsi_price);
   if(rsi_handle == INVALID_HANDLE) {
      LogMsg(LOG_ERROR, "Falha ao criar indicador RSI");
      return(INIT_FAILED);
   }
   ArraySetAsSeries(rsi_buffer, true);
   ind_rsi_period = cfg.rsi_period;  ind_rsi_price = cfg.rsi_price;

   // Media movel: da o sentido da mare, para o robo nao comprar contra a tendencia
   if(cfg.usar_tendencia) {
      mm_handle = iMA(_Symbol, _Period, cfg.mm_periodo, 0, (ENUM_MA_METHOD)cfg.mm_metodo, PRICE_CLOSE);
      if(mm_handle == INVALID_HANDLE) {
         LogMsg(LOG_ERROR, "Falha ao criar a media movel do filtro de tendencia");
         return(INIT_FAILED);
      }
      ArraySetAsSeries(mm_buffer, true);
      ind_mm_periodo = cfg.mm_periodo;  ind_mm_metodo = cfg.mm_metodo;
      LogMsg(LOG_INFO, StringFormat("Filtro de tendencia: media %s de %d periodos",
                                    EnumToString((ENUM_MA_METHOD)cfg.mm_metodo), cfg.mm_periodo));
   }

   // ATR: mede o tamanho do movimento normal, para o stop nao ser o mesmo todo dia
   if(cfg.usar_atr) {
      atr_handle = iATR(_Symbol, _Period, cfg.atr_periodo);
      if(atr_handle == INVALID_HANDLE) {
         LogMsg(LOG_ERROR, "Falha ao criar o ATR");
         return(INIT_FAILED);
      }
      ArraySetAsSeries(atr_buffer, true);
      ind_atr_periodo = cfg.atr_periodo;
      LogMsg(LOG_INFO, StringFormat("Stop por volatilidade: ATR(%d) x%.1f no stop, x%.1f no alvo",
                                    cfg.atr_periodo, cfg.atr_mult_sl, cfg.atr_mult_tp));
   }

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(10);

   // Verifica modo de preenchimento suportado pelo simbolo
   long filling_mode = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling_mode & SYMBOL_FILLING_FOK) != 0)
      trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((filling_mode & SYMBOL_FILLING_IOC) != 0)
      trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      trade.SetTypeFilling(ORDER_FILLING_RETURN);

   trade.SetAsyncMode(false);
   trade.LogLevel(LOG_LEVEL_NO);  // Desabilita logs automaticos do CTrade

   LogMsg(LOG_DEBUG, "------------------------------------------------------------");
   LogMsg(LOG_DEBUG, "CONFIGURACOES");
   LogMsg(LOG_DEBUG, StringFormat("RSI Periodo: %d | Sobrevenda: %.1f | Sobrecompra: %.1f", cfg.rsi_period, cfg.rsi_os, cfg.rsi_ob));
   LogMsg(LOG_DEBUG, StringFormat("Lote: %.2f | SL: %.0f pts | TP: %.0f pts", cfg.lote, cfg.sl, cfg.tp));
   LogMsg(LOG_DEBUG, StringFormat("Trailing Stop: %s", cfg.trailing ? "Ativo" : "Desativado"));
   LogMsg(LOG_DEBUG, "------------------------------------------------------------");
   LogMsg(LOG_DEBUG, StringFormat("Agressao (Fluxo): %s", cfg.usar_agressao ? "Ativo" : "Desativado"));
   LogMsg(LOG_DEBUG, StringFormat("Volume Profile: %s", cfg.usar_volume_profile ? "Ativo" : "Desativado"));
   LogMsg(LOG_DEBUG, "------------------------------------------------------------");

   if(UsarPainelExterno) {
      exportador = new CRSIExport();
      ExportarDadosPainelExterno();

      // Timer só funciona em modo live, não em backtest
      bool is_tester = MQLInfoInteger(MQL_TESTER);
      if(!is_tester)
         EventSetTimer(1);

      LogMsg(LOG_INFO, StringFormat("Painel Externo: ATIVO | Modo: %s", is_tester ? "BACKTEST" : "LIVE"));
      if(is_tester) {
         LogMsg(LOG_INFO, "BACKTEST: Exportacao via OnTick() (sem timer)");
         LogMsg(LOG_INFO, "BACKTEST: Arquivo = rsi_data_BACKTEST.json");
      }
      LogMsg(LOG_DEBUG, "[macOS] cd \"$HOME/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Include/MWM\" && python3 rsi_panel.py");
   }

   LogMsg(LOG_INFO, "============================================================");
   LogMsg(LOG_INFO, "RSI SNIPER inicializado com sucesso!");
   LogMsg(LOG_INFO, "============================================================");

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Timer                                                            |
//+------------------------------------------------------------------+
void OnTimer() {
   if(UsarPainelExterno && exportador != NULL) {
      // Importante: processar o comando do painel antes da exportacao. Se o EA
      // publica o JSON antigo antes de aplicar SALVAR_CONFIG, o painel ressincroniza
      // com valores antigos e a pessoa "volta" para a configuracao de partida.
      ProcessarComandosPainelExterno();
      AtualizarLucroDia();              // Atualiza lucro do dia (1x por segundo)
      ExportarDadosPainelExterno();     // Exporta dados para o painel (1x por segundo)
   }
}

//+------------------------------------------------------------------+
//| Finalizacao                                                      |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   EventKillTimer();

   // Log ANTES de fechar o arquivo
   LogMsg(LOG_INFO, "============================================================");
   LogMsg(LOG_INFO, "RSI SNIPER finalizado");
   LogMsg(LOG_INFO, "============================================================");

   if(rsi_handle != INVALID_HANDLE)
      IndicatorRelease(rsi_handle);

   if(mm_handle != INVALID_HANDLE)
      IndicatorRelease(mm_handle);

   if(atr_handle != INVALID_HANDLE)
      IndicatorRelease(atr_handle);

   if(exportador != NULL)
      delete exportador;

   // Fecha arquivo de log POR ÚLTIMO
   if(log_file_handle != INVALID_HANDLE) {
      FileClose(log_file_handle);
      log_file_handle = INVALID_HANDLE;
   }
}

//+------------------------------------------------------------------+
//| OnTrade - Chamado quando posicoes/ordens mudam                   |
//+------------------------------------------------------------------+
void OnTrade() {
   // BACKTEST: Exporta imediatamente quando posição abre/fecha
   if(UsarPainelExterno && exportador != NULL) {
      AtualizarLucroDia(true);  // Força atualização imediata
      ultima_exportacao = 0;    // Força exportação
      ExportarDadosPainelExterno();
   }
}

//+------------------------------------------------------------------+
//| OnTradeTransaction - Loga quando trade fecha (não soma, apenas log)
//| O cálculo do lucro é feito em CalcularLucroRealizadoHistorico()  |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result) {
   // Captura apenas deals (transações de fechamento)
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD) {
      // Verifica se é do nosso símbolo
      if(trans.symbol != _Symbol)
         return;

      // Busca informações do deal
      ulong deal_ticket = trans.deal;
      if(HistoryDealSelect(deal_ticket)) {
         // Verifica se é saída (fechamento de posição)
         ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal_ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT) {
            double lucro_deal = HistoryDealGetDouble(deal_ticket, DEAL_PROFIT);
            double comissao = HistoryDealGetDouble(deal_ticket, DEAL_COMMISSION);
            double swap = HistoryDealGetDouble(deal_ticket, DEAL_SWAP);
            double lucro_liquido = lucro_deal + comissao + swap;

            // Recalcula o acumulado do histórico (fonte única de verdade)
            AtualizarLucroDia(true);

            if(cfg.log_nivel >= LOG_INFO && lucro_deal != 0) {
               LogMsg(LOG_INFO, StringFormat("TRADE FECHADO | Lucro: %.2f | Comissao: %.2f | Total: %.2f | Acumulado: %.2f",
                      lucro_liquido, comissao, lucro_liquido, lucro_realizado));
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| OnTick - Logica principal                                        |
//+------------------------------------------------------------------+
void OnTick() {
   // ✅ BACKTEST: Atualiza e exporta a cada tick (OnTimer não funciona no backtest)
   AtualizarLucroDia();

   // ✅ COMMENT: Exibe dados em tempo real no gráfico (funciona no Strategy Tester Visual)
   int posicoes = 0;
   double lucro_posicoes = 0;
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket) && PositionGetString(POSITION_SYMBOL) == _Symbol) {
         posicoes++;
         lucro_posicoes += PositionGetDouble(POSITION_PROFIT);
      }
   }
   double rsi_comment = 0;
   if(CopyBuffer(rsi_handle, 0, 0, 1, rsi_buffer) > 0)
      rsi_comment = rsi_buffer[0];

   // Calcula saldo real = inicial + lucro (total em backtest, diário em live)
   double lucro_para_saldo = MQLInfoInteger(MQL_TESTER) ? lucro_total_backtest : lucro_realizado;
   double saldo_calculado = saldo_inicial + lucro_para_saldo;

   // Mostra LIVE ou BACKTEST no título do painel
   string modo_texto = MQLInfoInteger(MQL_TESTER) ? "BACKTEST" : "LIVE";

   // Em BACKTEST, mostra lucro total acumulado; em LIVE, mostra lucro do dia
   double lucro_exibir = MQLInfoInteger(MQL_TESTER) ? lucro_total_backtest : lucro_dia;
   string label_lucro = MQLInfoInteger(MQL_TESTER) ? "LUCRO TOTAL:  " : "LUCRO DO DIA: ";

   Comment(
      "═══════════════════════════════════════\n",
      "       RSI SNIPER - ", modo_texto, "\n",
      "═══════════════════════════════════════\n",
      "Saldo Inicial:   ", DoubleToString(saldo_inicial, 2), "\n",
      "Saldo Calculado: ", DoubleToString(saldo_calculado, 2), "\n",
      "───────────────────────────────────────\n",
      "Lucro Realizado: ", DoubleToString(lucro_realizado, 2), "\n",
      "Lucro Aberto:    ", DoubleToString(lucro_posicoes, 2), "\n",
      label_lucro, DoubleToString(lucro_exibir, 2), "\n",
      "───────────────────────────────────────\n",
      "Posicoes:  ", posicoes, "\n",
      "RSI:       ", DoubleToString(rsi_comment, 2), "\n",
      "═══════════════════════════════════════"
   );

   // Processa comandos do painel antes de exportar o estado, para que a
   // configuracao nova nao seja imediatamente sobrescrita pelo JSON antigo.
   if(UsarPainelExterno && exportador != NULL)
      ProcessarComandosPainelExterno();

   if(UsarPainelExterno && exportador != NULL)
      ExportarDadosPainelExterno();

   if(cfg.pausado)
      return;

   int total_positions = PositionsTotal();

   if(cfg.trailing && total_positions > 0)
      ApplyTrailingStop();

   // ✅ Calcula RSI ANTES de verificar cfg.max_pos (permite reset de flags)
   if(CopyBuffer(rsi_handle, 0, 0, 3, rsi_buffer) <= 0)
      return;

   double rsi_current = rsi_buffer[0];
   double rsi_previous = rsi_buffer[1];

   // Atualiza Agressao e Volume Profile (1x por segundo) - ANTES das verificações de return
   datetime nowSec = TimeTradeServer();
   if(nowSec != g_lastCalcSec) {
      g_lastCalcSec = nowSec;

      if(cfg.usar_agressao)
         g_agressao = CalcularAgressao();

      if(cfg.usar_volume_profile)
         g_volumeProfile = CalcularVolumeProfile();
   }

   // ✅ Reset de flags - permite novo sinal quando RSI voltar à zona neutra
   // buy_signal_sent reseta quando RSI SOBE de volta (acima de oversold + margem)
   if(buy_signal_sent && rsi_current > cfg.rsi_os + 5)
      buy_signal_sent = false;

   // sell_signal_sent reseta quando RSI CAI bem abaixo de overbought (zona neutra)
   if(sell_signal_sent && rsi_current < cfg.rsi_ob - 5)
      sell_signal_sent = false;

   // Bloqueia novas entradas se já atingiu cfg.max_pos (mas flags já foram resetadas)
   if(total_positions >= cfg.max_pos) {
      aguardando_entrada = false;  // Reset flag pois posição já existe
      return;
   }

   // A trava so vale enquanto a corretora nao respondeu. Se a posicao abriu e
   // fechou entre dois ticks, nenhum tick chegou a ver cfg.max_pos e o reset
   // acima nunca acontece — sem esta expiracao o EA travaria para sempre.
   if(aguardando_entrada && (TimeCurrent() - aguardando_desde) >= AGUARDA_ENTRADA_SEG) {
      LogMsg(LOG_DEBUG, "Trava de entrada expirou; ordem anterior ja se resolveu");
      aguardando_entrada = false;
   }

   // Bloqueia novas entradas enquanto aguarda ordem ser processada
   if(aguardando_entrada)
      return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   // SINAL DE COMPRA
   if(rsi_previous <= cfg.rsi_os && rsi_current > cfg.rsi_os) {
      if(!buy_signal_sent) {
         LogMsg(LOG_INFO, "------------------------------------------------------------");
         LogMsg(LOG_INFO, StringFormat("[SINAL] COMPRA DETECTADA | RSI: %.2f (cruzou acima de %.1f)", rsi_current, cfg.rsi_os));
         LogMsg(LOG_INFO, "------------------------------------------------------------");

         if(ConfirmacaoCompra()) {
            double d_sl, d_tp;
            DistanciasAtuais(d_sl, d_tp);   // fixos, ou proporcionais ao ATR
            double sl = ask - (d_sl * point);
            double tp = ask + (d_tp * point);
            AjustarStops(ask, sl, tp, true);
            double lote = NormalizarVolume(cfg.lote);

            aguardando_entrada = true;  // Bloqueia novas entradas
            aguardando_desde  = TimeCurrent();
            if(trade.Buy(lote, _Symbol, ask, sl, tp, "RSI Compra")) {
               // Calcula distâncias reais (após ajuste)
               double sl_pts = (ask - sl) / point;
               double tp_pts = (tp - ask) / point;
               LogMsg(LOG_INFO, StringFormat("COMPRA EXECUTADA | Preco: %s | Lote: %.2f | SL: %s (-%.0f pts) | TP: %s (+%.0f pts)",
                                            DoubleToString(ask, _Digits),
                                            lote,
                                            DoubleToString(sl, _Digits), sl_pts,
                                            DoubleToString(tp, _Digits), tp_pts));
               buy_signal_sent = true;
               sell_signal_sent = false;
               // OnTrade() será chamado automaticamente e fará a exportação
            } else {
               aguardando_entrada = false;  // Reset flag em caso de falha
               LogMsg(LOG_ERROR, StringFormat("Falha ao executar COMPRA: %s", trade.ResultRetcodeDescription()));
            }
         } else {
            LogMsg(LOG_INFO, StringFormat("[BLOQUEADO] COMPRA BLOQUEADA | Filtro de Agressao: %s (%.1f%% compra) | Necessario: >= %.0f%% e volume >= %.0f",
                                         g_agressao.direcao,
                                         g_agressao.pctCompra * 100,
                                         cfg.agr_pctmin * 100,
                                         cfg.agr_volmin));
         }
      }
   }

   // SINAL DE VENDA
   else if(rsi_previous >= cfg.rsi_ob && rsi_current < cfg.rsi_ob) {
      if(!sell_signal_sent) {
         LogMsg(LOG_INFO, "------------------------------------------------------------");
         LogMsg(LOG_INFO, StringFormat("[SINAL] VENDA DETECTADA | RSI: %.2f (cruzou abaixo de %.1f)", rsi_current, cfg.rsi_ob));
         LogMsg(LOG_INFO, "------------------------------------------------------------");

         if(ConfirmacaoVenda()) {
            double d_sl, d_tp;
            DistanciasAtuais(d_sl, d_tp);   // fixos, ou proporcionais ao ATR
            double sl = bid + (d_sl * point);
            double tp = bid - (d_tp * point);
            AjustarStops(bid, sl, tp, false);
            double lote = NormalizarVolume(cfg.lote);

            aguardando_entrada = true;  // Bloqueia novas entradas
            aguardando_desde  = TimeCurrent();
            if(trade.Sell(lote, _Symbol, bid, sl, tp, "RSI Venda")) {
               // Calcula distâncias reais (após ajuste)
               double sl_pts = (sl - bid) / point;
               double tp_pts = (bid - tp) / point;
               LogMsg(LOG_INFO, StringFormat("VENDA EXECUTADA | Preco: %s | Lote: %.2f | SL: %s (+%.0f pts) | TP: %s (-%.0f pts)",
                                            DoubleToString(bid, _Digits),
                                            lote,
                                            DoubleToString(sl, _Digits), sl_pts,
                                            DoubleToString(tp, _Digits), tp_pts));
               sell_signal_sent = true;
               buy_signal_sent = false;
               // OnTrade() será chamado automaticamente e fará a exportação
            } else {
               aguardando_entrada = false;  // Reset flag em caso de falha
               LogMsg(LOG_ERROR, StringFormat("Falha ao executar VENDA: %s", trade.ResultRetcodeDescription()));
            }
         } else {
            LogMsg(LOG_INFO, StringFormat("[BLOQUEADO] VENDA BLOQUEADA | Filtro de Agressao: %s (%.1f%% venda) | Necessario: >= %.0f%% e volume >= %.0f",
                                         g_agressao.direcao,
                                         g_agressao.pctVenda * 100,
                                         cfg.agr_pctmin * 100,
                                         cfg.agr_volmin));
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Exporta dados para o painel externo                              |
//+------------------------------------------------------------------+
void ExportarDadosPainelExterno() {
   // Atualiza tendencia e volatilidade sempre, nao so quando ha sinal,
   // para o painel refletir o estado real a cada atualizacao.
   g_tendencia = LerTendencia();
   LerATRPontos();

   // BACKTEST: Exporta a cada N barras para evitar throttle baseado em tempo real
   // GetTickCount() retorna tempo REAL do sistema, não tempo simulado no backtest
   // Isso causava bloqueio de quase todas as exportações durante backtest rápido

   static int ticks_desde_export = 0;
   bool is_tester = MQLInfoInteger(MQL_TESTER);

   if(is_tester) {
      // No backtest: exporta a cada 5 ticks para capturar posições rápidas
      ticks_desde_export++;
      if(ticks_desde_export < 5 && ultima_exportacao != 0)
         return;
      ticks_desde_export = 0;
   } else {
      // LIVE: Throttle baseado em tempo real (funciona corretamente)
      uint agora = GetTickCount();
      uint diff = agora - ultima_exportacao;
      if(diff < (uint)cfg.export_ms && diff < 60000)
         return;
   }

   ultima_exportacao = GetTickCount();

   string status = cfg.pausado ? "PAUSADO" : "ATIVO";
   int posicoes = 0;
   double lucro_aberto = 0.0;

   // Conta posicoes do simbolo atual e lucro aberto
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket)) {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol) {
            posicoes++;
            lucro_aberto += PositionGetDouble(POSITION_PROFIT);
         }
      }
   }

   double rsi_atual = 0.0;
   if(CopyBuffer(rsi_handle, 0, 0, 1, rsi_buffer) > 0)
      rsi_atual = rsi_buffer[0];

   // Obter saldo da conta (calculado, pois ACCOUNT_BALANCE não atualiza no Tester)
   // Em BACKTEST usa lucro total acumulado; em LIVE usa lucro do dia
   double lucro_para_saldo = MQLInfoInteger(MQL_TESTER) ? CalcularLucroTotalHistorico() : lucro_realizado;
   double saldo = saldo_inicial + lucro_para_saldo;

   // Determinar status do sinal
   string sinal_status = "Aguardando sinal...";
   if(rsi_atual <= cfg.rsi_os)
      sinal_status = "RSI em SOBREVENDA (" + DoubleToString(rsi_atual, 1) + ")";
   else if(rsi_atual >= cfg.rsi_ob)
      sinal_status = "RSI em SOBRECOMPRA (" + DoubleToString(rsi_atual, 1) + ")";
   else if(rsi_atual > cfg.rsi_os && rsi_atual < 45)
      sinal_status = "RSI subindo (" + DoubleToString(rsi_atual, 1) + ")";
   else if(rsi_atual < cfg.rsi_ob && rsi_atual > 55)
      sinal_status = "RSI caindo (" + DoubleToString(rsi_atual, 1) + ")";
   else
      sinal_status = "RSI neutro (" + DoubleToString(rsi_atual, 1) + ")";

   if(posicoes > 0)
      sinal_status = "Em operacao: " + IntegerToString(posicoes) + " pos";

   // Prepara logs na ordem correta (mais novo primeiro) para o buffer circular
   string logs_ordenados[];
   ArrayResize(logs_ordenados, g_log_count);
   for(int i = 0; i < g_log_count; i++) {
      // Lê do mais recente para o mais antigo
      int idx = (g_log_index - 1 - i + LOG_BUFFER_SIZE) % LOG_BUFFER_SIZE;
      logs_ordenados[i] = g_log_buffer[idx];
   }

   exportador.SetParametros(cfg);
      exportador.ExportarDados(
      status, _Symbol, posicoes, lucro_dia, rsi_atual,
      cfg.lote, cfg.sl, cfg.tp,
      cfg.trailing, cfg.trailing_pts,
      // Buffer de logs ordenado (mais novo primeiro)
      logs_ordenados, g_log_count,
      // Novos dados de monitoramento (opcionais)
      saldo, lucro_aberto,
      g_agressao.pctCompra, g_agressao.pctVenda,
      g_agressao.volumeTotal, g_agressao.direcao,
      g_volumeProfile.poc, g_volumeProfile.vah, g_volumeProfile.val,
      g_volumeProfile.zona, sinal_status,
      cfg.usar_agressao, cfg.usar_volume_profile,
      lucro_total_backtest,  // Lucro total (apenas backtest)
      // Filtro de tendencia e stop por volatilidade
      cfg.usar_tendencia, cfg.usar_atr,
      g_mm_valor, g_atr_valor, g_tendencia
   );
}

//+------------------------------------------------------------------+
//| Recria os indicadores quando o painel muda periodo/metodo.       |
//| Handle nasce com o parametro fixo: mudar exige criar de novo.    |
//+------------------------------------------------------------------+
void RecriarIndicadoresSePreciso() {
   if(cfg.rsi_period != ind_rsi_period || cfg.rsi_price != ind_rsi_price) {
      int novo = iRSI(_Symbol, _Period, cfg.rsi_period, (ENUM_APPLIED_PRICE)cfg.rsi_price);
      if(novo == INVALID_HANDLE) {
         LogMsg(LOG_ERROR, StringFormat("RSI(%d) invalido: mantendo o anterior", cfg.rsi_period));
         cfg.rsi_period = ind_rsi_period;  cfg.rsi_price = ind_rsi_price;
      } else {
         if(rsi_handle != INVALID_HANDLE) IndicatorRelease(rsi_handle);
         rsi_handle = novo;  ArraySetAsSeries(rsi_buffer, true);
         ind_rsi_period = cfg.rsi_period;  ind_rsi_price = cfg.rsi_price;
         LogMsg(LOG_INFO, StringFormat("RSI recriado: %d periodos", cfg.rsi_period));
      }
   }

   if(cfg.usar_tendencia && (cfg.mm_periodo != ind_mm_periodo || cfg.mm_metodo != ind_mm_metodo)) {
      int novo = iMA(_Symbol, _Period, cfg.mm_periodo, 0, (ENUM_MA_METHOD)cfg.mm_metodo, PRICE_CLOSE);
      if(novo == INVALID_HANDLE) {
         LogMsg(LOG_ERROR, "Media movel invalida: mantendo a anterior");
         cfg.mm_periodo = ind_mm_periodo;  cfg.mm_metodo = ind_mm_metodo;
      } else {
         if(mm_handle != INVALID_HANDLE) IndicatorRelease(mm_handle);
         mm_handle = novo;  ArraySetAsSeries(mm_buffer, true);
         ind_mm_periodo = cfg.mm_periodo;  ind_mm_metodo = cfg.mm_metodo;
         LogMsg(LOG_INFO, StringFormat("Media movel recriada: %d periodos", cfg.mm_periodo));
      }
   }

   if(cfg.usar_atr && cfg.atr_periodo != ind_atr_periodo) {
      int novo = iATR(_Symbol, _Period, cfg.atr_periodo);
      if(novo == INVALID_HANDLE) {
         LogMsg(LOG_ERROR, "ATR invalido: mantendo o anterior");
         cfg.atr_periodo = ind_atr_periodo;
      } else {
         if(atr_handle != INVALID_HANDLE) IndicatorRelease(atr_handle);
         atr_handle = novo;  ArraySetAsSeries(atr_buffer, true);
         ind_atr_periodo = cfg.atr_periodo;
         LogMsg(LOG_INFO, StringFormat("ATR recriado: %d periodos", cfg.atr_periodo));
      }
   }
}

//+------------------------------------------------------------------+
//| Ponte painel -> robo: le e aplica um comando por chamada.        |
//| Formato SALVAR_CONFIG:chave=valor;chave=valor (o posicional      |
//| antigo ainda e aceito). Chave desconhecida ou valor fora do      |
//| limite e ignorada, mantendo o valor que ja estava valendo.       |
//+------------------------------------------------------------------+
void ProcessarComandosPainelExterno() {
   string comando = exportador.LerComando();

   if(comando == "")
      return;

   exportador.ProcessarComando(comando, cfg, cfg_original);
}

//+------------------------------------------------------------------+
//| Atualiza lucro do dia (com throttle adaptativo)                  |
//+------------------------------------------------------------------+
void AtualizarLucroDia(bool forcar = false) {
   static int ticks_desde_atualizacao = 0;
   bool is_tester = MQLInfoInteger(MQL_TESTER);

   if(!forcar) {
      if(is_tester) {
         // BACKTEST: Atualiza a cada 5 ticks para capturar mudanças rápidas
         ticks_desde_atualizacao++;
         if(ticks_desde_atualizacao < 5)
            return;
         ticks_desde_atualizacao = 0;
      } else {
         // LIVE: Throttle baseado em tempo real
         uint agora = GetTickCount();
         if((agora - ultima_atualizacao_lucro < 500) && agora > ultima_atualizacao_lucro)
            return;
         ultima_atualizacao_lucro = agora;
      }
   }

   // ⚠️ IMPORTANTE: AccountInfoDouble(ACCOUNT_BALANCE) NÃO atualiza em tempo real no Strategy Tester!
   // Solução: Calcular lucro manualmente usando HistoryDealGetDouble
   // Fonte: https://www.mql5.com/en/forum/234668

   // Calcula lucro realizado a partir do histórico de deals (funciona no Strategy Tester)
   lucro_realizado = CalcularLucroRealizadoHistorico();

   // Calcula lucro flutuante das posições abertas
   double lucro_flutuante = 0.0;
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket)) {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol) {
            lucro_flutuante += PositionGetDouble(POSITION_PROFIT);
         }
      }
   }

   // Lucro do dia = realizado (trades fechados do dia) + flutuante (posições abertas)
   lucro_dia = lucro_realizado + lucro_flutuante;

   // Em BACKTEST, calcula também o lucro total acumulado (todo o histórico)
   if(MQLInfoInteger(MQL_TESTER)) {
      lucro_total_backtest = CalcularLucroTotalHistorico() + lucro_flutuante;
   }
}

//+------------------------------------------------------------------+
//| Calcula lucro realizado do histórico de deals (apenas do dia)    |
//| Usa DEAL_PROFIT diretamente - funciona em LIVE e BACKTEST        |
//+------------------------------------------------------------------+
double CalcularLucroRealizadoHistorico() {
   double lucro_total = 0.0;

   // Calcula início do dia atual (00:00:00)
   datetime agora = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(agora, dt);
   dt.hour = 0;
   dt.min = 0;
   dt.sec = 0;
   datetime inicio_do_dia = StructToTime(dt);

   // Seleciona histórico apenas do dia atual
   if(!HistorySelect(inicio_do_dia, agora)) {
      return 0.0;
   }

   int total_deals = HistoryDealsTotal();

   for(int i = 0; i < total_deals; i++) {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      ENUM_DEAL_TYPE dtype = (ENUM_DEAL_TYPE)HistoryDealGetInteger(ticket, DEAL_TYPE);
      ENUM_DEAL_ENTRY dentry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      string dsymbol = HistoryDealGetString(ticket, DEAL_SYMBOL);

      // Ignora balance e deals de outros símbolos
      if(dtype == DEAL_TYPE_BALANCE) continue;
      if(dsymbol != _Symbol) continue;

      // Apenas deals de saída (fechamento) tem lucro
      if(dentry == DEAL_ENTRY_OUT || dentry == DEAL_ENTRY_INOUT) {
         double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
         double commission = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         double swap = HistoryDealGetDouble(ticket, DEAL_SWAP);

         lucro_total += profit + commission + swap;
      }
   }

   return lucro_total;
}

//+------------------------------------------------------------------+
//| Calcula lucro TOTAL do histórico (todo o backtest, sem filtro)   |
//| Usado apenas em BACKTEST para mostrar lucro acumulado total      |
//+------------------------------------------------------------------+
double CalcularLucroTotalHistorico() {
   double lucro = 0.0;

   // Seleciona TODO o histórico (desde o início)
   if(!HistorySelect(0, TimeCurrent())) {
      return 0.0;
   }

   int total_deals = HistoryDealsTotal();

   for(int i = 0; i < total_deals; i++) {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      ENUM_DEAL_TYPE dtype = (ENUM_DEAL_TYPE)HistoryDealGetInteger(ticket, DEAL_TYPE);
      ENUM_DEAL_ENTRY dentry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      string dsymbol = HistoryDealGetString(ticket, DEAL_SYMBOL);

      // Ignora balance e deals de outros símbolos
      if(dtype == DEAL_TYPE_BALANCE) continue;
      if(dsymbol != _Symbol) continue;

      // Apenas deals de saída (fechamento) tem lucro
      if(dentry == DEAL_ENTRY_OUT || dentry == DEAL_ENTRY_INOUT) {
         double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
         double commission = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         double swap = HistoryDealGetDouble(ticket, DEAL_SWAP);

         lucro += profit + commission + swap;
      }
   }

   return lucro;
}

//+------------------------------------------------------------------+
//| Trailing Stop                                                    |
//+------------------------------------------------------------------+
void ApplyTrailingStop() {
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);

      if(PositionSelectByTicket(ticket)) {
         if(PositionGetString(POSITION_SYMBOL) != _Symbol)
            continue;

         double position_sl = PositionGetDouble(POSITION_SL);
         double position_tp = PositionGetDouble(POSITION_TP);
         ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

         if(type == POSITION_TYPE_BUY) {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double new_sl = bid - (cfg.trailing_pts * point);

            if((position_sl == 0 || new_sl > position_sl) && new_sl < bid) {
               if(!trade.PositionModify(ticket, new_sl, position_tp)) {
                  if(cfg.log_nivel >= LOG_DEBUG)
                     Print("[Trailing] Falha ao modificar BUY #", ticket, ": ", trade.ResultRetcodeDescription());
               }
            }
         }
         else if(type == POSITION_TYPE_SELL) {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double new_sl = ask + (cfg.trailing_pts * point);

            if((position_sl == 0 || new_sl < position_sl) && new_sl > ask) {
               if(!trade.PositionModify(ticket, new_sl, position_tp)) {
                  if(cfg.log_nivel >= LOG_DEBUG)
                     Print("[Trailing] Falha ao modificar SELL #", ticket, ": ", trade.ResultRetcodeDescription());
               }
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
