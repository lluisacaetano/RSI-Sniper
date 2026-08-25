//+------------------------------------------------------------------+
//|                      RSIExport.mqh                               |
//|                                                                  |
//| Biblioteca de comunicação entre o EA e o painel Python           |
//| - Exporta dados em JSON para Common/Files                        |
//| - Lê comandos do painel (PAUSAR, FECHAR_TUDO, etc)               |
//| - Usa arquivos separados para BACKTEST e LIVE (evita conflito)   |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025"
#property version   "1.00"

#include <Trade/Trade.mqh>

// Quanto tempo um comando do painel continua valendo. Cinco minutos cobrem com
// folga o caso legitimo (o painel manda enquanto o EA ainda esta carregando) e
// nao deixam comando esquecido na pasta virar armadilha para a proxima sessao.
#define VALIDADE_COMANDO_SEG 300

//+------------------------------------------------------------------+
//| Configurações do EA em struct para facilitar passagem de dados   |
//| O painel pode modificar esses valores em tempo real              |
//+------------------------------------------------------------------+
struct SRSIConfig {
   bool   pausado;              // true = operações bloqueadas
   double lote;                 // tamanho da posição
   double sl;                   // stop loss em pontos
   double tp;                   // take profit em pontos
   bool   trailing;             // usar trailing stop?
   double trailing_pts;         // distância do trailing em pontos
   bool   usar_agressao;        // filtro de fluxo de ordens
   bool   usar_volume_profile;  // filtro de volume profile
   bool   usar_tendencia;       // filtro de media movel (so opera a favor da mare)
   bool   usar_atr;             // stop e alvo proporcionais a volatilidade
   // --- ajustaveis pelo painel a partir da v2 ---
   int    rsi_period;           // periodos do RSI (recria o handle ao mudar)
   int    rsi_price;            // ENUM_APPLIED_PRICE como inteiro
   double rsi_os;               // nivel de sobrevenda
   double rsi_ob;               // nivel de sobrecompra
   int    agr_janela;           // janela de leitura do fluxo (segundos)
   double agr_volmin;           // volume minimo na janela
   double agr_pctmin;           // percentual para confirmar direcao (0..1)
   int    vp_barras;            // candles do perfil de volume
   int    vp_passo;             // agrupamento do perfil em ticks
   double vp_margem;            // zona neutra em torno do POC
   int    mm_periodo;           // periodos da media movel (recria o handle)
   int    mm_metodo;            // ENUM_MA_METHOD como inteiro (recria o handle)
   int    atr_periodo;          // periodos do ATR (recria o handle)
   double atr_mult_sl;          // multiplicador do ATR no stop
   double atr_mult_tp;          // multiplicador do ATR no alvo
   int    max_pos;              // maximo de posicoes simultaneas
   int    log_nivel;            // ENUM_LOG_LEVEL como inteiro
   int    export_ms;            // intervalo de exportacao para o painel
};

class CRSIExport {
private:
   SRSIConfig cfg_atual;      // copia usada so para publicar os valores no painel
   bool       tem_cfg;
   string arquivo_dados;
   string arquivo_comandos;
   datetime ultimo_comando_lido;
   string ultimo_comando_processado;
   // Eco do ultimo comando aceito, para o painel confirmar que chegou aqui.
   // Sem isso o painel so sabe que gravou o arquivo, nao que o robo leu.
   string ultimo_comando_ts;
   int    ultimo_comando_qtd;
   int contador_export;
   int contador_erros;
   CTrade trade_fechar;  // Reutilizado para fechar posicoes

public:
   CRSIExport() {
      // Usa arquivos diferentes para BACKTEST vs LIVE (evita conflito)
      string sufixo = MQLInfoInteger(MQL_TESTER) ? "_BACKTEST" : "_LIVE";
      arquivo_dados = "rsi_data" + sufixo + ".json";
      arquivo_comandos = "rsi_commands" + sufixo + ".txt";

      tem_cfg = false;
      ultimo_comando_lido = 0;
      ultimo_comando_processado = "";
      ultimo_comando_ts = "";
      ultimo_comando_qtd = 0;
      contador_export = 0;
      contador_erros = 0;
      trade_fechar.LogLevel(LOG_LEVEL_NO);  // Desabilita logs automaticos

      string caminho = TerminalInfoString(TERMINAL_COMMONDATA_PATH) + "\\Files\\";
      bool is_tester = MQLInfoInteger(MQL_TESTER);

      Print("========================================");
      Print("  RSI EXPORT - Configuracao de Arquivos");
      Print("========================================");
      Print("  Modo: ", is_tester ? "BACKTEST" : "LIVE");
      Print("  Pasta de dados: ", caminho);
      Print("  Arquivo de dados: ", arquivo_dados);
      Print("  Arquivo de comandos: ", arquivo_comandos);
      Print("========================================");

      // Remove arquivo antigo se existir
      if(FileIsExist(arquivo_dados, FILE_COMMON)) {
         if(!FileDelete(arquivo_dados, FILE_COMMON))
            Print("[AVISO] Nao foi possivel remover arquivo antigo: ", GetLastError());
      }

      // Cria arquivo inicial imediatamente para o painel detectar
      CriarArquivoInicial();
   }

   //+------------------------------------------------------------------+
   //| Cria arquivo inicial para o painel detectar                      |
   //+------------------------------------------------------------------+
   void CriarArquivoInicial() {
      int handle = FileOpen(arquivo_dados, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ);

      if(handle == INVALID_HANDLE) {
         Print("[ERRO] Nao foi possivel criar arquivo de dados: ", GetLastError());
         return;
      }

      // Usa hora do servidor no backtest (acompanha tempo simulado)
      datetime agora = MQLInfoInteger(MQL_TESTER) ? TimeTradeServer() : TimeLocal();
      string timestamp_atual = TimeToString(agora, TIME_DATE|TIME_SECONDS);

      string json = "{\n";
      json += "  \"status\": \"INICIANDO\",\n";
      json += "  \"ativo\": \"" + _Symbol + "\",\n";
      json += "  \"posicoes\": 0,\n";
      json += "  \"lucro_dia\": 0.00,\n";
      json += "  \"rsi\": 0.00,\n";
      json += "  \"lote\": 1.00,\n";
      json += "  \"stoploss\": 200,\n";
      json += "  \"takeprofit\": 350,\n";
      json += "  \"usar_trailing\": true,\n";
      json += "  \"trailing_pontos\": 150,\n";
      json += "  \"ultimo_comando\": \"\",\n";
      json += "  \"ultimo_comando_ts\": \"\",\n";
      json += "  \"ultimo_comando_qtd\": 0,\n";
      json += "  \"saldo\": 0.00,\n";
      json += "  \"lucro_aberto\": 0.00,\n";
      json += "  \"agressao_compra\": 0.0,\n";
      json += "  \"agressao_venda\": 0.0,\n";
      json += "  \"agressao_vol\": 0,\n";
      json += "  \"agressao_direcao\": \"\",\n";
      json += "  \"vp_poc\": 0.00,\n";
      json += "  \"vp_vah\": 0.00,\n";
      json += "  \"vp_val\": 0.00,\n";
      json += "  \"vp_zona\": \"\",\n";
      json += "  \"sinal_status\": \"Inicializando...\",\n";
      json += "  \"usar_agressao\": false,\n";
      json += "  \"usar_volume_profile\": false,\n";
      json += "  \"usar_tendencia\": false,\n";
      json += "  \"usar_atr\": false,\n";
      json += "  \"mm_valor\": 0,\n";
      json += "  \"atr_pontos\": 0,\n";
      json += "  \"tendencia\": \"\",\n";
      json += "  \"logs\": [],\n";
      json += "  \"timestamp\": \"" + timestamp_atual + "\"\n";
      json += "}";

      FileWriteString(handle, json);
      FileFlush(handle);
      FileClose(handle);
   }

   //+------------------------------------------------------------------+
   //| Exporta dados para o painel Python                               |
   //+------------------------------------------------------------------+
   // Guarda os valores correntes para o painel exibir e editar
   void SetParametros(const SRSIConfig &c) { cfg_atual = c; tem_cfg = true; }

   void ExportarDados(string status, string ativo, int posicoes,
                     double lucro_dia_valor, double rsi_atual,
                     double lote, double sl, double tp,
                     bool usar_trailing, double trailing_pts,
                     string &log_buffer[], int log_count,
                     // Novos parametros de monitoramento
                     double saldo = 0, double lucro_aberto = 0,
                     double agressao_compra = 0, double agressao_venda = 0,
                     double agressao_vol = 0, string agressao_direcao = "NEUTRO",
                     double vp_poc = 0, double vp_vah = 0, double vp_val = 0,
                     string vp_zona = "INDEFINIDO", string sinal_status = "Aguardando...",
                     bool usar_agressao = true, bool usar_volume_profile = true,
                     double lucro_total = 0,    // Lucro total (apenas backtest)
                     // Filtro de tendencia (media movel) e stop por volatilidade (ATR)
                     bool usar_tendencia = false, bool usar_atr = false,
                     double mm_valor = 0, double atr_pontos = 0,
                     string tendencia = "") {

      // Usa hora do servidor no backtest (acompanha tempo simulado)
      datetime agora = MQLInfoInteger(MQL_TESTER) ? TimeTradeServer() : TimeLocal();
      string timestamp_atual = TimeToString(agora, TIME_DATE|TIME_SECONDS);

      int handle = FileOpen(arquivo_dados, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ);

      if(handle == INVALID_HANDLE) {
         if(contador_erros % 100 == 0)
            Print("[ERRO] Falha ao abrir arquivo de dados: ", GetLastError());
         contador_erros++;
         return;
      }

      string json = "{\n";
      json += "  \"status\": \"" + status + "\",\n";
      json += "  \"ativo\": \"" + ativo + "\",\n";
      json += "  \"posicoes\": " + IntegerToString(posicoes) + ",\n";
      json += "  \"lucro_dia\": " + DoubleToString(lucro_dia_valor, 2) + ",\n";
      json += "  \"rsi\": " + DoubleToString(rsi_atual, 2) + ",\n";
      json += "  \"lote\": " + DoubleToString(lote, 2) + ",\n";
      json += "  \"stoploss\": " + DoubleToString(sl, 0) + ",\n";
      json += "  \"takeprofit\": " + DoubleToString(tp, 0) + ",\n";
      json += "  \"usar_trailing\": " + (usar_trailing ? "true" : "false") + ",\n";
      json += "  \"trailing_pontos\": " + DoubleToString(trailing_pts, 0) + ",\n";
      json += "  \"ultimo_comando\": \"" + ultimo_comando_processado + "\",\n";
      json += "  \"ultimo_comando_ts\": \"" + ultimo_comando_ts + "\",\n";
      json += "  \"ultimo_comando_qtd\": " + IntegerToString(ultimo_comando_qtd) + ",\n";
      // Novos campos de monitoramento
      json += "  \"saldo\": " + DoubleToString(saldo, 2) + ",\n";
      json += "  \"lucro_aberto\": " + DoubleToString(lucro_aberto, 2) + ",\n";
      json += "  \"agressao_compra\": " + DoubleToString(agressao_compra * 100, 1) + ",\n";
      json += "  \"agressao_venda\": " + DoubleToString(agressao_venda * 100, 1) + ",\n";
      json += "  \"agressao_vol\": " + DoubleToString(agressao_vol, 0) + ",\n";
      json += "  \"agressao_direcao\": \"" + agressao_direcao + "\",\n";
      json += "  \"vp_poc\": " + DoubleToString(vp_poc, 2) + ",\n";
      json += "  \"vp_vah\": " + DoubleToString(vp_vah, 2) + ",\n";
      json += "  \"vp_val\": " + DoubleToString(vp_val, 2) + ",\n";
      json += "  \"vp_zona\": \"" + vp_zona + "\",\n";
      json += "  \"sinal_status\": \"" + sinal_status + "\",\n";
      json += "  \"usar_agressao\": " + (usar_agressao ? "true" : "false") + ",\n";
      json += "  \"usar_volume_profile\": " + (usar_volume_profile ? "true" : "false") + ",\n";
      json += "  \"usar_tendencia\": " + (usar_tendencia ? "true" : "false") + ",\n";
      json += "  \"usar_atr\": " + (usar_atr ? "true" : "false") + ",\n";
      json += "  \"mm_valor\": " + DoubleToString(mm_valor, _Digits) + ",\n";
      json += "  \"atr_pontos\": " + DoubleToString(atr_pontos, 1) + ",\n";
      json += "  \"tendencia\": \"" + tendencia + "\",\n";

      // Bloco de parametros ajustaveis pelo painel
      if(tem_cfg) {
         json += "  \"p_rsi_period\": "  + IntegerToString(cfg_atual.rsi_period) + ",\n";
         json += "  \"p_rsi_price\": "   + IntegerToString(cfg_atual.rsi_price) + ",\n";
         json += "  \"p_rsi_os\": "      + DoubleToString(cfg_atual.rsi_os, 1) + ",\n";
         json += "  \"p_rsi_ob\": "      + DoubleToString(cfg_atual.rsi_ob, 1) + ",\n";
         json += "  \"p_agr_janela\": "  + IntegerToString(cfg_atual.agr_janela) + ",\n";
         json += "  \"p_agr_volmin\": "  + DoubleToString(cfg_atual.agr_volmin, 1) + ",\n";
         json += "  \"p_agr_pctmin\": "  + DoubleToString(cfg_atual.agr_pctmin, 2) + ",\n";
         json += "  \"p_vp_barras\": "   + IntegerToString(cfg_atual.vp_barras) + ",\n";
         json += "  \"p_vp_passo\": "    + IntegerToString(cfg_atual.vp_passo) + ",\n";
         json += "  \"p_vp_margem\": "   + DoubleToString(cfg_atual.vp_margem, 1) + ",\n";
         json += "  \"p_mm_periodo\": "  + IntegerToString(cfg_atual.mm_periodo) + ",\n";
         json += "  \"p_mm_metodo\": "   + IntegerToString(cfg_atual.mm_metodo) + ",\n";
         json += "  \"p_atr_periodo\": " + IntegerToString(cfg_atual.atr_periodo) + ",\n";
         json += "  \"p_atr_mult_sl\": " + DoubleToString(cfg_atual.atr_mult_sl, 2) + ",\n";
         json += "  \"p_atr_mult_tp\": " + DoubleToString(cfg_atual.atr_mult_tp, 2) + ",\n";
         json += "  \"p_max_pos\": "     + IntegerToString(cfg_atual.max_pos) + ",\n";
         json += "  \"p_log_nivel\": "   + IntegerToString(cfg_atual.log_nivel) + ",\n";
         json += "  \"p_export_ms\": "   + IntegerToString(cfg_atual.export_ms) + ",\n";
      }

      // Lucro total (apenas em backtest)
      if(MQLInfoInteger(MQL_TESTER)) {
         json += "  \"lucro_total\": " + DoubleToString(lucro_total, 2) + ",\n";
      }

      // Array de logs (últimas N mensagens)
      json += "  \"logs\": [\n";
      for(int i = 0; i < log_count; i++) {
         string virgula = (i < log_count - 1) ? "," : "";
         // Escapa caracteres especiais para JSON valido
         string linha = log_buffer[i];
         StringReplace(linha, "\\", "\\\\");  // Escapa barras primeiro
         StringReplace(linha, "\"", "\\\"");  // Escapa aspas corretamente
         StringReplace(linha, "\n", "\\n");   // Escapa quebras de linha
         StringReplace(linha, "\r", "\\r");   // Escapa retorno de carro
         StringReplace(linha, "\t", "\\t");   // Escapa tabs
         json += "    \"" + linha + "\"" + virgula + "\n";
      }
      json += "  ],\n";

      json += "  \"timestamp\": \"" + timestamp_atual + "\"\n";
      json += "}";

      FileWriteString(handle, json);
      FileFlush(handle);
      FileClose(handle);

      contador_export++;
   }

   //+------------------------------------------------------------------+
   //| Le comando do painel Python                                      |
   //+------------------------------------------------------------------+
   string LerComando() {
      if(!FileIsExist(arquivo_comandos, FILE_COMMON))
         return "";

      int handle = FileOpen(arquivo_comandos, FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_WRITE|FILE_SHARE_READ);

      if(handle == INVALID_HANDLE)
         return "";

      string conteudo = "";
      while(!FileIsEnding(handle)) {
         conteudo += FileReadString(handle) + "\n";
      }
      FileClose(handle);

      string linhas[];
      int num_linhas = StringSplit(conteudo, '\n', linhas);

      if(num_linhas < 2) {
         FileDelete(arquivo_comandos, FILE_COMMON);
         return "";
      }

      string comando = linhas[0];
      string timestamp_str = linhas[1];
      // Linha 3 (opcional): identidade unica do comando. O carimbo da linha 2 so
      // tem precisao de segundo, entao dois comandos no mesmo segundo carregam o
      // mesmo texto - e o eco de um confirmava o outro no painel. Painel antigo
      // nao manda esta linha: ai o eco continua sendo o carimbo.
      string ident = (num_linhas >= 3) ? linhas[2] : "";

      StringTrimLeft(comando);
      StringTrimRight(comando);
      StringTrimLeft(timestamp_str);
      StringTrimRight(timestamp_str);
      StringTrimLeft(ident);
      StringTrimRight(ident);

      if(comando == "" || timestamp_str == "") {
         FileDelete(arquivo_comandos, FILE_COMMON);
         return "";
      }

      datetime timestamp_comando = StringToTime(timestamp_str);

      // Comando velho nao e para este robo. Sem esta janela, um arquivo esquecido
      // na Common/Files vale para sempre: um PARAR_EA de 19/08 ficou armado na
      // pasta e desligaria sozinho o proximo robo que subisse ali, dias depois,
      // sem motivo visivel na tela. A janela e larga o bastante para o caso
      // legitimo - o painel manda enquanto o EA ainda esta carregando.
      // No testador o relogio e o do periodo simulado (2025), muito atras do
      // relogio do painel, entao a diferenca da negativa e o comando passa.
      if(!MQLInfoInteger(MQL_TESTER) &&
         TimeLocal() - timestamp_comando > VALIDADE_COMANDO_SEG) {
         FileDelete(arquivo_comandos, FILE_COMMON);
         return "";
      }

      // Estritamente menor: o arquivo e apagado assim que lido, entao um
      // comando novo no MESMO segundo do anterior e um comando legitimo, nao
      // repeticao. Com <= aqui ele era descartado calado - e era esse o
      // salvamento que "voltava sozinho" para os valores antigos.
      if(timestamp_comando < ultimo_comando_lido) {
         // Apaga tambem quando ignora. Sem isso o arquivo fica parado na pasta
         // para sempre e o painel nao consegue distinguir "o robo ja tratou"
         // de "o robo nunca leu".
         FileDelete(arquivo_comandos, FILE_COMMON);
         return "";
      }

      ultimo_comando_lido = timestamp_comando;
      // Eco para o painel casar com o que enviou: a identidade quando o painel
      // manda uma, o carimbo quando e painel antigo.
      ultimo_comando_ts = (ident != "") ? ident : timestamp_str;

      FileDelete(arquivo_comandos, FILE_COMMON);

      return comando;
   }

   //+------------------------------------------------------------------+
   //| Processa comando recebido (versao com struct)                    |
   //+------------------------------------------------------------------+
   bool ProcessarComando(string comando, SRSIConfig &config, const SRSIConfig &config_orig) {

      if(comando == "")
         return false;

      bool sucesso = false;

      if(comando == "PAUSAR") {
         config.pausado = !config.pausado;
         if(config.pausado) {
            Print("[PAUSADO] ROBO PAUSADO | Operacoes bloqueadas");
         } else {
            Print("[ATIVO] ROBO RETOMADO | Operacoes ativas");
         }
         ultimo_comando_processado = config.pausado ? "PAUSADO" : "RETOMADO";
         sucesso = true;
      }

      else if(comando == "FECHAR_TUDO") {
         Print("[ALERTA] FECHANDO TODAS AS POSICOES...");
         FecharTodasPosicoes();
         Print("[OK] Todas as posicoes foram fechadas");
         ultimo_comando_processado = "POSICOES FECHADAS";
         sucesso = true;
      }

      else if(StringFind(comando, "SALVAR_CONFIG:") == 0) {
         string parametros = StringSubstr(comando, 14);

         // Formato novo: chave=valor;chave=valor. Imune a mudanca de ordem e a
         // campos que o painel nao conheca. O formato antigo (posicional) segue
         // aceito para nao quebrar paineis desatualizados.
         if(StringFind(parametros, "=") >= 0) {
            string pares[];
            int n = StringSplit(parametros, ';', pares);
            int aplicados = 0;
            for(int i = 0; i < n; i++) {
               string kv[];
               if(StringSplit(pares[i], '=', kv) != 2) continue;
               string k = kv[0];
               string v = kv[1];
               StringTrimLeft(k); StringTrimRight(k);
               StringTrimLeft(v); StringTrimRight(v);
               double d = StringToDouble(v);
               bool   b = (v == "1" || v == "true" || v == "True");

               if(k == "sl")               config.sl = d;
               else if(k == "tp")          config.tp = d;
               else if(k == "trailing_pts")config.trailing_pts = d;
               else if(k == "trailing")    config.trailing = b;
               else if(k == "lote")        config.lote = d;
               else if(k == "usar_agressao")       config.usar_agressao = b;
               else if(k == "usar_volume_profile") config.usar_volume_profile = b;
               else if(k == "usar_tendencia")      config.usar_tendencia = b;
               else if(k == "usar_atr")            config.usar_atr = b;
               else if(k == "rsi_period")  config.rsi_period = (int)d;
               else if(k == "rsi_price")   config.rsi_price  = (int)d;
               else if(k == "rsi_os")      config.rsi_os = d;
               else if(k == "rsi_ob")      config.rsi_ob = d;
               else if(k == "agr_janela")  config.agr_janela = (int)d;
               else if(k == "agr_volmin")  config.agr_volmin = d;
               else if(k == "agr_pctmin")  config.agr_pctmin = d;
               else if(k == "vp_barras")   config.vp_barras = (int)d;
               else if(k == "vp_passo")    config.vp_passo = (int)d;
               else if(k == "vp_margem")   config.vp_margem = d;
               else if(k == "mm_periodo")  config.mm_periodo = (int)d;
               else if(k == "mm_metodo")   config.mm_metodo = (int)d;
               else if(k == "atr_periodo") config.atr_periodo = (int)d;
               else if(k == "atr_mult_sl") config.atr_mult_sl = d;
               else if(k == "atr_mult_tp") config.atr_mult_tp = d;
               else if(k == "max_pos")     config.max_pos = (int)d;
               else if(k == "log_nivel")   config.log_nivel = (int)d;
               else if(k == "export_ms")   config.export_ms = (int)d;
               else continue;
               aplicados++;
            }
            Print("[CONFIG] ", aplicados, " parametro(s) aplicado(s) pelo painel");
            ultimo_comando_processado = "CONFIG SALVA";
            ultimo_comando_qtd = aplicados;   // o painel mostra este numero, nao o dele
            sucesso = true;
         }
         else {
            string valores[];
            int total = StringSplit(parametros, ',', valores);

            if(total >= 4) {
               config.sl = StringToDouble(valores[0]);
               config.tp = StringToDouble(valores[1]);
               config.trailing_pts = StringToDouble(valores[2]);
               config.trailing = (valores[3] == "1");

               if(total >= 6) {
                  config.usar_agressao = (valores[4] == "1");
                  config.usar_volume_profile = (valores[5] == "1");
               }
               if(total >= 7) config.lote = StringToDouble(valores[6]);
               if(total >= 9) {
                  config.usar_tendencia = (valores[7] == "1");
                  config.usar_atr = (valores[8] == "1");
               }

               Print("[CONFIG] CONFIGURACOES SALVAS (formato antigo):");
               Print("    Lote: ", DoubleToString(config.lote, 2), " | SL: ", config.sl, " pts | TP: ", config.tp, " pts");
               ultimo_comando_processado = "CONFIG SALVA";
               ultimo_comando_qtd = total;
               sucesso = true;
            }
         }
      }

      else if(comando == "RESETAR_CONFIG") {
         config = config_orig;      // struct inteira, sem esquecer campo novo
         config.pausado = false;
         Print("[RESET] Parametros restaurados aos valores de inicializacao");
         ultimo_comando_processado = "CONFIG RESETADA";
         sucesso = true;
      }

      else if(comando == "PARAR_EA") {
         Print("════════════════════════════════════════");
         Print("  EA REMOVIDO PELO PAINEL");
         Print("════════════════════════════════════════");
         ultimo_comando_processado = "EA PARADO";
         sucesso = true;
         // Remove o EA do gráfico
         ExpertRemove();
      }

      return sucesso;
   }

   //+------------------------------------------------------------------+
   //| Fecha todas as posicoes do simbolo atual                         |
   //+------------------------------------------------------------------+
   void FecharTodasPosicoes() {
      int fechadas = 0;

      for(int i = PositionsTotal() - 1; i >= 0; i--) {
         ulong ticket = PositionGetTicket(i);
         if(PositionSelectByTicket(ticket)) {
            if(PositionGetString(POSITION_SYMBOL) == _Symbol) {
               if(trade_fechar.PositionClose(ticket)) {
                  fechadas++;
                  Print("   Posicao #", ticket, " fechada");
               }
            }
         }
      }

      if(fechadas > 0)
         Print("  Total de posicoes fechadas: ", fechadas);
      else
         Print("  Nenhuma posicao encontrada para fechar");
   }
};
