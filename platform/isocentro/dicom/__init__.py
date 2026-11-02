"""O que veio do TPS, como número: a geometria, os cortes, a malha e a dose.

``dicom_rt`` modela os objetos RT (TC, RP, RS, RD), que chegam já lidos por
``adaptadores/dicom`` (o arquivo pela ``leitura``, o DB Daemon do ARIA pela
``rede``, desde a R-58). ``ct_series`` monta o volume, ``corpo3d`` a malha do
corpo pelo contorno EXTERNAL, ``dose3d`` soma doses numa grade comum e ``dvh``
calcula o histograma.

Desenhar mora em ``isocentro/desenho/`` desde a R-58 (corte 3), e depende deste
pacote, nunca o contrário. A geometria (sistema de coordenadas, orientação do
paciente, espaçamento entre cortes) fica AQUI, uma vez só: o desenho lê a da
série em vez de refazê-la, que é onde os dois lados se afastariam em silêncio.
"""
