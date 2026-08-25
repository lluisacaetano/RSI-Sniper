"""
Exercita para ONDE o painel fala, sem MetaTrader nenhum.

O Wine cria mais de um perfil em drive_c/users e cada um tem a sua
Common/Files. So um deles recebe os arquivos do robo, e nao e sempre o mesmo:
o MetaTrader aberto pelo aplicativo roda como "user", o wine chamado na linha
de comando roda como o usuario do Mac. O painel precisa acompanhar essa troca
em vez de decidir uma vez e teimar - foi por teimar que um SALVAR_CONFIG de 25
parametros ficou parado numa pasta morta.

Aqui os dois perfis sao pastas de verdade num diretorio temporario, e o robo e
simulado publicando o JSON dele em um deles.
"""
import sys, os, json, time, tempfile, pathlib

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import rsi_panel as m

falhas = []

def checa(nome, obtido, esperado):
    ok = obtido == esperado
    print(("  PASSOU  " if ok else "  FALHOU  ") + nome)
    if not ok:
        print(f"            esperava {esperado!r}")
        print(f"            obtido   {obtido!r}")
        falhas.append(nome)

# ── um Wine de mentira, com os dois perfis que existem na maquina de verdade ──
tmp = pathlib.Path(tempfile.mkdtemp(prefix="rsi_wine_"))
RELATIVO = "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users"
perfis = {}
for nome in ("user", "luisacaetano"):
    p = tmp / RELATIVO / nome / "AppData/Roaming/MetaQuotes/Terminal/Common/Files"
    p.mkdir(parents=True)
    perfis[nome] = p

def robo_publica(perfil, modo="LIVE", idade_seg=0, **extra):
    """O robo escrevendo o JSON dele na Common/Files do perfil em que roda."""
    d = {"timestamp": "2026.08.24 22:00:00", "status": "ATIVO", "lote": 1.0,
         "stoploss": 200, "takeprofit": 350, "trailing_pontos": 150,
         "ultimo_comando_ts": "", "ultimo_comando_qtd": 0}
    d.update(extra)
    alvo = perfis[perfil] / f"rsi_data_{modo}.json"
    alvo.write_text(json.dumps(d))
    if idade_seg:
        quando = time.time() - idade_seg
        os.utime(alvo, (quando, quando))
    return alvo

app = m.RSIPanelModern()
app.withdraw()
app.home_base = tmp          # o painel passa a enxergar o Wine de mentira
app.sistema = "Darwin"
app.confirmacao_pendente = None

def onde_le():
    return pathlib.Path(app.data_file).parent

def onde_grava():
    return pathlib.Path(app.command_file).parent

print("\n=== 1. RSI_COMMON_PATH manda mais que a deteccao ===")
forcada = tmp / "pasta_escolhida_na_mao"
forcada.mkdir()
os.environ["RSI_COMMON_PATH"] = str(forcada)
checa("respeita a variavel de ambiente", app._detectar_caminho(), str(forcada))
del os.environ["RSI_COMMON_PATH"]

print("\n=== 2. painel abre com o robo no perfil errado e o robo muda de casa ===")
robo_publica("luisacaetano", "BACKTEST", idade_seg=300)   # rastro velho
app.common_path = str(perfis["luisacaetano"])
app.modo_atual = "BACKTEST"
app._atualizar_arquivos()
checa("comeca apontando para o rastro velho", onde_le(), perfis["luisacaetano"])

robo_publica("user", "LIVE")                              # robo acorda no outro perfil
app._atualizar_dados()                                    # um ciclo do loop de 250 ms
app.update()
checa("migrou de pasta sozinho", onde_le(), perfis["user"])
checa("e trocou de canal junto", app.modo_atual, "LIVE")
checa("comando passa a sair na pasta certa", onde_grava(), perfis["user"])

print("\n=== 3. enviar comando nao confia na pasta de quando o painel abriu ===")
app.common_path = str(perfis["luisacaetano"])             # painel teimando de novo
app._atualizar_arquivos()
robo_publica("user", "LIVE")                              # robo esta aqui, agora
app._enviar_comando("PAUSAR")
entregue = perfis["user"] / "rsi_commands_LIVE.txt"
orfaos = sorted(f.name for f in perfis["luisacaetano"].glob("rsi_commands_*"))
checa("comando chegou na pasta do robo", entregue.exists(), True)
checa("nao ficou orfao na pasta morta", orfaos, [])
entregue.unlink(missing_ok=True)

print("\n=== 4. nao migra no meio de uma confirmacao pendente ===")
app.common_path = str(perfis["luisacaetano"])
app._atualizar_arquivos()
app.confirmacao_pendente = {'ts': 'x', 'enviados': 25,
                            'prazo': time.monotonic() + 60,
                            'arquivo': app.command_file}
robo_publica("user", "LIVE")
app._revisar_caminho()
checa("ficou onde estava ate a pendencia fechar", onde_le(), perfis["luisacaetano"])
app.confirmacao_pendente = None

print("\n=== 5. nao troca de pasta por ruido: so por dado mais fresco ===")
robo_publica("user", "LIVE")                              # pasta atual, quente
app.common_path = str(perfis["user"])
app._atualizar_arquivos()
robo_publica("luisacaetano", "LIVE", idade_seg=600)       # a outra, fria
app._revisar_caminho()
checa("ignorou a pasta mais velha", onde_le(), perfis["user"])

print("\n" + ("TODOS PASSARAM" if not falhas else f"FALHAS: {falhas}"))
app.destroy()
sys.exit(1 if falhas else 0)
