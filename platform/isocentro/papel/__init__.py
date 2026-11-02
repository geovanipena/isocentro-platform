"""O que sai IMPRESSO e vai grampeado para a sala de tratamento.

``ficha_pdf`` (a ficha técnica), ``capa_pdf`` (a Ficha de Tratamento),
``drr`` (as páginas de setup do 600CD) e ``rodape``, o "Impresso em …" que é o
mesmo no pé de toda página de todo PDF do serviço.

Mudar qualquer coisa aqui — ordem de campo, texto de célula, geometria — muda o
papel que alguém confere com o paciente já na mesa, e por isso **exige aviso ao
usuário**, mesmo quando a mudança foi pedida. É a regra do CLAUDE.md, e este
pacote existe em parte para que ela tenha um endereço: se o diff toca
``papel/``, o papel mudou.
"""
