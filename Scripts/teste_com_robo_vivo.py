"""
Ponta a ponta: cada parametro, cada leitura e cada botao do painel conferidos
contra o robo de verdade.

Diferente dos outros dois testes, este NAO simula o robo: exige um EA rodando.
O jeito mais estavel de ter um por varios minutos e o testador em modo visual:

    wine terminal64.exe "/config:C:\\Program Files\\MetaTrader 5\\config\\painel_vivo_tester.ini"

Depois:  python3 teste_com_robo_vivo.py
"""
import sys, os, json, time, pathlib

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import rsi_panel as m

# ── parametro do painel -> chave que o robo publica de volta ──
ESPELHO = {
    'lote': 'lote', 'sl': 'stoploss', 'tp': 'takeprofit',
    'trailing_pts': 'trailing_pontos', 'trailing': 'usar_trailing',
    'usar_agressao': 'usar_agressao', 'usar_volume_profile': 'usar_volume_profile',
    'usar_tendencia': 'usar_tendencia', 'usar_atr': 'usar_atr',
    'rsi_period': 'p_rsi_period', 'rsi_price': 'p_rsi_price',
    'rsi_os': 'p_rsi_os', 'rsi_ob': 'p_rsi_ob',
    'agr_janela': 'p_agr_janela', 'agr_volmin': 'p_agr_volmin',
    'agr_pctmin': 'p_agr_pctmin', 'vp_barras': 'p_vp_barras',
    'vp_passo': 'p_vp_passo', 'vp_margem': 'p_vp_margem',
    'mm_periodo': 'p_mm_periodo', 'mm_metodo': 'p_mm_metodo',
    'atr_periodo': 'p_atr_periodo', 'atr_mult_sl': 'p_atr_mult_sl',
    'atr_mult_tp': 'p_atr_mult_tp', 'max_pos': 'p_max_pos',
}
ALVO_TEXTO = {
    'lote': '2', 'sl': '333', 'tp': '777', 'trailing_pts': '111',
    'rsi_period': '7', 'rsi_os': '25', 'rsi_ob': '75',
    'agr_janela': '2', 'agr_volmin': '600', 'agr_pctmin': '0.8',
    'vp_barras': '90', 'vp_passo': '7', 'vp_margem': '15',
    'mm_periodo': '21', 'atr_periodo': '9',
    'atr_mult_sl': '2.5', 'atr_mult_tp': '4.5', 'max_pos': '3',
}
ALVO_MARCA = {'trailing': False, 'usar_agressao': True,
              'usar_volume_profile': True, 'usar_tendencia': True, 'usar_atr': True}
MARCADORES = lambda app: {
    'trailing': app.trailing_var, 'usar_agressao': app.agressao_var,
    'usar_volume_profile': app.volume_profile_var,
    'usar_tendencia': app.tendencia_var, 'usar_atr': app.atr_var}

falhas = []

def checa(nome, ok, detalhe=""):
    print(("  PASSOU  " if ok else "  FALHOU  ") + nome + (f"   {detalhe}" if detalhe else ""))
    if not ok:
        falhas.append(nome)
    return ok

def igual(env, rec):
    if isinstance(env, bool):
        return bool(rec) == env
    try:
        return abs(float(env) - float(rec)) < 1e-6
    except (TypeError, ValueError):
        return str(env) == str(rec)

app = m.RSIPanelModern()
app.withdraw()

def le_json():
    """
    Le pelo mesmo caminho do painel.

    O robo trunca e reescreve o JSON a cada publicacao; quem le naquele instante
    pega arquivo pela metade. O painel resolve isso com 3 tentativas dentro de
    _ler_dados - ler de outro jeito aqui seria testar um leitor que nao existe.
    """
    for _ in range(10):
        d = app._ler_dados()
        if d:
            return d
        time.sleep(0.1)
    raise AssertionError("robo publicou 10 arquivos ilegiveis seguidos")

def exige_robo_vivo(fase):
    """Robo morto no meio do teste vira divergencia falsa em todo campo."""
    if not os.path.exists(app.data_file):
        print(f"\n  ABORTADO em '{fase}': nenhum robo publicando.")
        app.destroy(); sys.exit(2)
    idade = time.time() - os.path.getmtime(app.data_file)
    if idade > 15:
        print(f"\n  ABORTADO em '{fase}': o robo parou de publicar ha {idade:.0f}s.")
        print("  (o backtest visual chegou ao fim? suba de novo antes de repetir)")
        app.destroy(); sys.exit(2)

def bombeia(segundos):
    """Roda o loop do painel de verdade pelo tempo pedido."""
    limite = time.time() + segundos
    while time.time() < limite:
        app._atualizar_dados(); app.update(); time.sleep(0.25)

def espera_publicacao(referencia, segundos=15):
    limite = time.time() + segundos
    ultimo = le_json()
    while time.time() < limite:
        app._atualizar_dados(); app.update(); time.sleep(0.25)
        ultimo = le_json()
        if ultimo.get('timestamp') != referencia:
            return ultimo
    return ultimo

def salva_e_espera(segundos=20):
    """Clica em SALVAR e espera o robo confirmar. Devolve o aviso da tela."""
    app._salvar_config()
    limite = time.time() + segundos
    while app.confirmacao_pendente and time.time() < limite:
        app._atualizar_dados(); app.update(); time.sleep(0.25)
    return app.lbl_status_config.cget("text")

# ══ 1. destino: o painel tem que achar sozinho onde o robo publica ══
print("\n=== 1. destino ===")
app._sincronizar_destino(forcar=True)
print(f"  pasta: {app._rotulo_pasta()}   canal: {app.modo_atual}")
exige_robo_vivo("destino")
checa("achou um robo publicando agora",
      time.time() - os.path.getmtime(app.data_file) < 15)

# ══ 2. RESETAR primeiro: a partida passa a ser sempre a mesma ══
print("\n=== 2. partida ===")
app._enviar_comando("RESETAR_CONFIG")
espera_publicacao(le_json().get('timestamp')); bombeia(1)
partida = le_json()
print(f"  RSI {partida.get('p_rsi_period')} {partida.get('p_rsi_os')}/{partida.get('p_rsi_ob')}"
      f" | SL {partida.get('stoploss')} | TP {partida.get('takeprofit')}")

# ══ 3. todos os parametros de uma vez ══
print("\n=== 3. os 25 parametros ===")
for chave, texto in ALVO_TEXTO.items():
    campo = app.entry_trailing if chave == 'trailing_pts' else (
        app.entries.get(chave) or app.entries_param.get(chave))
    campo.delete(0, 'end'); campo.insert(0, texto)
for chave, ligado in ALVO_MARCA.items():
    MARCADORES(app)[chave].set(ligado)
menus_alvo = {}
for chave, (menu, opcoes) in app.menus_param.items():
    rotulos = list(opcoes.keys())
    novo = next((r for r in rotulos if r != menu.get()), rotulos[0])
    menu.set(novo); menus_alvo[chave] = opcoes[novo]
aviso = salva_e_espera()
print(f"  painel disse: {aviso}")
checa("robo confirmou o salvamento", "aplicou" in aviso, aviso)

exige_robo_vivo("conferencia dos 25")
dados = le_json()
esperado = dict(ALVO_TEXTO); esperado.update(ALVO_MARCA); esperado.update(menus_alvo)
divergentes = [c for c in sorted(ESPELHO) if not igual(esperado[c], dados.get(ESPELHO[c]))]
for c in sorted(ESPELHO):
    print(f"     {c:22s} {str(esperado[c]):>8s} -> {str(dados.get(ESPELHO[c])):>10s}"
          f"   {'ok' if c not in divergentes else 'DIVERGE'}")
checa("os 25 parametros bateram", not divergentes, str(divergentes))

# ══ 4. monitoramento: o que a tela mostra e o que o robo publicou ══
print("\n=== 4. monitoramento (leituras ao vivo) ===")
# O rotulo e pintado a partir de UMA publicacao; no backtest visual o robo ja
# publicou outra antes de eu conseguir ler o arquivo. Entao o rotulo vale se
# corresponder a publicacao de antes OU a de depois do ciclo - o que ele nao
# pode e mostrar numero que o robo nunca publicou.
bombeia(1)
d_antes = le_json()
app._atualizar_dados(); app.update()
d = le_json()
leituras = [
    ('ativo',         app.info_labels['ativo'].cget("text"),        str(d.get('ativo'))),
    ('posicoes',      app.info_labels['posicoes'].cget("text"),     str(d.get('posicoes'))),
    ('rsi',           app.info_labels['rsi'].cget("text"),          f"{d.get('rsi', 0):.2f}"),
    ('lucro_dia',     app.info_labels['lucro_dia'].cget("text"),    f"R$ {d.get('lucro_dia', 0):.2f}"),
    ('saldo',         app.info_labels['saldo'].cget("text"),        f"R$ {d.get('saldo', 0):.2f}"),
    ('lucro_aberto',  app.info_labels['lucro_aberto'].cget("text"), f"R$ {d.get('lucro_aberto', 0):.2f}"),
]
if app.modo_atual == "BACKTEST":
    leituras.append(('lucro_total', app.info_labels['lucro_total'].cget("text"),
                     f"R$ {d.get('lucro_total', 0):.2f}"))
formata = {'ativo': lambda v: str(v), 'posicoes': lambda v: str(v),
           'rsi': lambda v: f"{v:.2f}"}
for nome, na_tela, no_json in leituras:
    f = formata.get(nome, lambda v: f"R$ {v:.2f}")
    aceitos = {no_json, f(d_antes.get(nome, 0))}
    checa(f"{nome:14s} tela={na_tela!r}", na_tela in aceitos,
          f"robo publicou {sorted(aceitos)}")
checa("conexao acesa com robo vivo", app.lbl_conexao.cget("text") == "CONECTADO",
      app.lbl_conexao.cget("text"))

# ══ 5. cada filtro: liga, confere; desliga, confere ══
print("\n=== 5. liga/desliga de cada filtro ===")
for chave in ('usar_agressao', 'usar_volume_profile', 'usar_tendencia', 'usar_atr'):
    for ligado in (True, False):
        exige_robo_vivo(f"{chave}={ligado}")
        MARCADORES(app)[chave].set(ligado)
        salva_e_espera()
        bombeia(1)
        no_robo = le_json().get(ESPELHO[chave])
        checa(f"{chave:20s} {'ligar ' if ligado else 'desligar'}",
              bool(no_robo) == ligado, f"robo={no_robo}")

# ══ 6. RESETAR devolve exatamente a configuracao de partida ══
print("\n=== 6. RESETAR ===")
exige_robo_vivo("resetar")
app._enviar_comando("RESETAR_CONFIG")
espera_publicacao(le_json().get('timestamp')); bombeia(1)
depois = le_json()
voltou = [c for c in sorted(ESPELHO) if not igual(partida.get(ESPELHO[c]), depois.get(ESPELHO[c]))]
for c in voltou:
    print(f"     {c:22s} partida={partida.get(ESPELHO[c])!r} agora={depois.get(ESPELHO[c])!r}")
checa(f"os {len(ESPELHO)} campos voltaram a partida", not voltou, str(voltou))

# ══ 7. PAUSAR / RETOMAR ══
print("\n=== 7. PAUSAR / RETOMAR ===")
exige_robo_vivo("pausar")
estado0 = depois.get('status')
app._enviar_comando("PAUSAR")
d1 = espera_publicacao(depois.get('timestamp'))
checa("pausou", d1.get('status') != estado0, f"{estado0} -> {d1.get('status')}")
app._enviar_comando("PAUSAR")
d2 = espera_publicacao(d1.get('timestamp'))
checa("retomou", d2.get('status') == estado0, f"{d1.get('status')} -> {d2.get('status')}")

# ══ 8. dois salvamentos no mesmo segundo ══
print("\n=== 8. dois salvamentos no mesmo segundo ===")
exige_robo_vivo("mesmo segundo")
antes_ts = le_json().get('timestamp')
app.entries['sl'].delete(0, 'end'); app.entries['sl'].insert(0, "444")
app._salvar_config(); id1 = app.confirmacao_pendente['ts']
app.entries['sl'].delete(0, 'end'); app.entries['sl'].insert(0, "555")
app._salvar_config(); id2 = app.confirmacao_pendente['ts']
checa("cada comando tem identidade propria", id1 != id2, f"...{id1[-8:]} / ...{id2[-8:]}")
limite = time.time() + 20
while app.confirmacao_pendente and time.time() < limite:
    app._atualizar_dados(); app.update(); time.sleep(0.25)
final = espera_publicacao(antes_ts); bombeia(1); final = le_json()
checa("o robo ficou com o ultimo valor", str(final.get('stoploss')) in ("555", "555.0"),
      f"stop={final.get('stoploss')}")

# ══ 9. FECHAR_TUDO ══
print("\n=== 9. FECHAR TUDO ===")
exige_robo_vivo("fechar tudo")
ref = le_json().get('timestamp')
app._enviar_comando("FECHAR_TUDO")
d3 = espera_publicacao(ref)
checa("robo reconheceu o comando", d3.get('ultimo_comando') == "POSICOES FECHADAS",
      f"ultimo_comando={d3.get('ultimo_comando')!r}")

# ══ 10. PARAR_EA (por ultimo: derruba o robo) ══
print("\n=== 10. PARAR EA (encerra o robo) ===")
exige_robo_vivo("parar ea")
ref = le_json().get('timestamp')
app._enviar_comando("PARAR_EA")
d4 = espera_publicacao(ref, segundos=8)
# No testador, ExpertRemove() encerra o teste na hora e o eco nao chega a ser
# publicado - a prova de que o comando pegou e o robo parar de publicar. Ao
# vivo o EA ainda exporta antes de sair, e ai o eco aparece.
parou = time.time() - os.path.getmtime(app.data_file) > 5
checa("robo parou depois do PARAR_EA",
      parou or d4.get('ultimo_comando') == "EA PARADO",
      f"ultimo_comando={d4.get('ultimo_comando')!r}, parado={parou}")

print("\n" + ("PAINEL E ROBO 100% COERENTES" if not falhas else f"FALHAS ({len(falhas)}): {falhas}"))
app.destroy()
sys.exit(1 if falhas else 0)
