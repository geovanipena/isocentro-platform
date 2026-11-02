"""ISOCENTRO — o código do app, que até 09/09/2026 morava solto na raiz.

A raiz tinha 61 módulos ``.py`` misturados com dado de execução (os JSON que o
app grava ao lado de si), saída de build e documentação. Não era só desconforto
visual: sem uma fronteira, qualquer arquivo novo na pasta parecia fazer parte do
programa, e a pergunta "de onde vem este dado?" não tinha resposta legível.

A divisão é por **papel no fluxo**, não por tecnologia:

    banco/      de onde vem o dado clínico, nos três degraus
    dominio/    a regra e o cálculo do serviço
    dicom/      ler e renderizar o que veio do TPS
    papel/      o que é impresso e vai grampeado para a sala
    interface/  o que o usuário vê e opera
    dados/      o que o app grava e relê dele mesmo
    raiz.py     onde tudo isso mora em disco

O ``run_gui.py`` continua na raiz do projeto: é a porta de entrada, é o que o
``Isocentro.spec`` aponta, e porta de entrada dentro do pacote seria uma a menos
para achar.
"""
