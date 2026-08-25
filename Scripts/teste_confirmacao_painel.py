"""
Exercita o ciclo salvar -> confirmar do painel sem MetaTrader nenhum.

O robo e simulado por dois arquivos: o JSON que ele publica e o TXT de comando
que ele apaga ao ler. Sao os mesmos dois arquivos do sistema de verdade, entao
o que passa aqui vale la.
"""
import sys, os, json, time, tempfile, pathlib

BASE = "/Users/luisacaetano/DEV/RSI_Sniper_Instalacao/Scripts"
sys.path.insert(0, BASE)
import rsi_panel as m

falhas = []

def checa(nome, obtido, esperado_contem):
    ok = esperado_contem in obtido
    print(("  PASSOU  " if ok else "  FALHOU  ") + nome)
    if not ok:
        print(f"            esperava conter {esperado_contem!r}")
        print(f"            obtido          {obtido!r}")
        falhas.append(nome)

app = m.RSIPanelModern()
app.withdraw()

tmp = tempfile.mkdtemp(prefix="rsi_teste_")
app.common_path = tmp
app._atualizar_arquivos()
app.confirmacao_pendente = None

def aviso():
    return app.lbl_status_config.cget("text")

def publica_json(**extra):
    d = {"timestamp": "2026.08.24 22:00:00", "status": "ATIVO", "lote": 1.0,
         "stoploss": 200, "takeprofit": 350, "trailing_pontos": 150}
    d.update(extra)
    pathlib.Path(app.data_file).write_text(json.dumps(d))

print("\n=== 1. salvar nao pode mais anunciar sucesso sozinho ===")
publica_json(ultimo_comando_ts="", ultimo_comando_qtd=0)
app._salvar_config()
app.update()
checa("mostra que esta aguardando o robo", aviso(), "aguardando o robô")
pend = app.confirmacao_pendente
assert pend, "deveria haver confirmacao pendente"
print(f"            (enviou {pend['enviados']} parametros, ts={pend['ts']})")
checa("arquivo de comando foi gravado", str(os.path.exists(app.command_file)), "True")

print("\n=== 2. robo responde: painel usa a contagem DELE, nao a do painel ===")
os.remove(app.command_file)                      # o robo apaga ao ler
publica_json(ultimo_comando_ts=pend['ts'], ultimo_comando_qtd=25)
app._atualizar_dados_uma_vez = None
app._conferir_confirmacao(json.loads(pathlib.Path(app.data_file).read_text()))
app.update()
checa("confirma com o numero do robo", aviso(), "robô aplicou 25 parâmetros")
checa("pendencia foi encerrada", str(app.confirmacao_pendente), "None")

print("\n=== 3. robo parado: arquivo fica em disco e o painel denuncia ===")
publica_json(ultimo_comando_ts="", ultimo_comando_qtd=0)
app._salvar_config()
app.update()
checa("volta a aguardar", aviso(), "aguardando o robô")
app.confirmacao_pendente['prazo'] = time.monotonic() - 1     # estoura o prazo
app._conferir_confirmacao(json.loads(pathlib.Path(app.data_file).read_text()))
app.update()
checa("avisa que o robo nao leu", aviso(), "não leu o comando")

print("\n=== 4. robo de versao antiga: consumiu o arquivo, mas nao ecoa ===")
publica_json()                                    # JSON sem as chaves de eco
app._salvar_config()
app.update()
os.remove(app.command_file)                       # robo antigo leu e apagou
app.confirmacao_pendente['prazo'] = time.monotonic() - 1
app._conferir_confirmacao(json.loads(pathlib.Path(app.data_file).read_text()))
app.update()
checa("reconhece robo antigo", aviso(), "recompile o EA")

print("\n=== 5. campos nao sao repintados enquanto a confirmacao nao chega ===")
app.entries['sl'].delete(0, 'end'); app.entries['sl'].insert(0, "999")
app.confirmacao_pendente = {'ts': 'x', 'enviados': 25,
                            'prazo': time.monotonic() + 60}
publica_json(stoploss=200, ultimo_comando_ts="", ultimo_comando_qtd=0)
app._atualizar_dados()
app.update()
checa("valor digitado sobreviveu ao ciclo", app.entries['sl'].get(), "999")

app.confirmacao_pendente = None

print("\n=== 6. dois comandos no mesmo segundo nao podem virar confirmacao falsa ===")
# O robo descarta comando cujo carimbo nao e mais novo que o do ultimo lido. Se o
# painel carimba so ate o segundo, o segundo salvamento dentro do mesmo segundo e
# jogado fora - e o eco que sobra no JSON e o do comando ANTERIOR. Casar com ele
# faz o painel anunciar sucesso de um comando que o robo nunca aplicou, e os
# campos voltam aos valores antigos. Foi o defeito relatado.
publica_json(ultimo_comando_ts="", ultimo_comando_qtd=0)
app._salvar_config()                      # primeiro salvamento
primeiro = app.confirmacao_pendente['ts']
os.remove(app.command_file)               # robo leu e aplicou
publica_json(ultimo_comando_ts=primeiro, ultimo_comando_qtd=25)
app._conferir_confirmacao(json.loads(pathlib.Path(app.data_file).read_text()))

app.entries['sl'].delete(0, 'end'); app.entries['sl'].insert(0, "888")
app._salvar_config()                      # segundo salvamento, mesmo segundo
segundo = app.confirmacao_pendente['ts']
checa("cada comando tem identidade propria", str(segundo != primeiro), "True")

# o robo descartou o segundo: apagou o arquivo e manteve o eco do primeiro
os.remove(app.command_file)
publica_json(stoploss=200, ultimo_comando_ts=primeiro, ultimo_comando_qtd=25)
app.confirmacao_pendente['prazo'] = time.monotonic() - 1
app._conferir_confirmacao(json.loads(pathlib.Path(app.data_file).read_text()))
app.update()
ok = "aplicou" not in aviso()
print(("  PASSOU  " if ok else "  FALHOU  ") + "nao anuncia sucesso com eco alheio")
if not ok:
    print(f"            painel disse: {aviso()!r}")
    falhas.append("confirmacao falsa")
app.confirmacao_pendente = None

print("\n" + ("TODOS PASSARAM" if not falhas else f"FALHAS: {falhas}"))
app.destroy()
sys.exit(1 if falhas else 0)
