"""De onde vem o dado clínico — os TRÊS DEGRAUS, e nesta ordem.

    capa_db      o data warehouse ``variandw``, que é a fonte (leitura apenas)
    capa_espelho o que o banco JÁ respondeu sobre AQUELE paciente
    capa_dados   os relatórios exportados, só como último recurso

O terceiro lê CSV e não fala SQL, e ainda assim mora aqui: separá-lo por
tecnologia esconderia que os três são a MESMA decisão, tomada em ordem, com a
tela dizendo qual degrau valeu. Reserva usada é reserva anunciada — quem lê
``capa_dados`` isolado num pacote "arquivos" não tem como saber disso.

``tratamento_db``, ``atividades_db`` e ``gatilho_db`` são o mesmo warehouse por
outras perguntas; ``banco_local`` guarda o que ele respondeu, para reproduzir
uma consulta longe da rede da clínica.
"""
