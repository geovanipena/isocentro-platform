---
name: clinica
description: Ferramentas que falam com a clínica — banco (gravar_banco.py, atividades.py), ARIA e DICOM (sondar_dicom.py, descobrir_dicom.bat). Use ao mexer em capa_db, banco_local, tratamento_db, exportação automática, C-GET/C-MOVE, AE Title, variandw, ou sempre que a tarefa exigir identidade de rede (runas /netonly).
---

# Ferramentas de clínica: banco, ARIA e DICOM

**Leia `tools/LEIAME_CLINICA.md` agora** — é onde mora o detalhe de cada uma, e
ele é versionado (esta skill vive em `.claude/`, que o git ignora: se sumir numa
reinstalação, o conteúdo continua no repositório).

```
sed -n '1,200p' tools/LEIAME_CLINICA.md
```

## O que decidir antes de escrever qualquer comando

Três coisas que o texto detalha e que erram caro se forem supostas:

1. **Nenhuma delas roda desta máquina.** Está fora do domínio, o SSPI é
   recusado. Quem roda é o usuário — então o entregável não é a saída da
   ferramenta, é **o comando pronto para copiar** mais o que conferir na saída.
2. **O que exige identidade de rede vai pelo `.bat`**, nunca `python tools/x.py`
   dentro de um `runas`: o console do `runas` fecha ao terminar e leva o
   relatório junto, na hora exata em que ele importa.
3. **Avisar em voz alta que a bola está com o usuário.** Sem isso a sessão fica
   esperando um resultado que ninguém foi buscar.

## O porquê de existirem

Todas nasceram da mesma regra: **não decidir sobre o que não se mediu**. O nome
das tabelas de atividade muda de versão para versão do ARIA; escolher C-GET ou
C-MOVE pelo manual é a armadilha do `mapear_gatilho.py` outra vez; e o caminho
de instalação no servidor seria chute meu. Elas perguntam em vez de supor, e são
**somente leitura** — isso não é detalhe, é a característica principal: o
`variandw` é o sistema clínico.
