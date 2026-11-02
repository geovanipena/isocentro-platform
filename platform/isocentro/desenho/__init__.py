"""Desenhar o que o modelo calculou: o corte, o DVH e o corpo 3D, em PNG.

Importado por ``papel/`` e por ``interface/``, que mostram as MESMAS imagens —
o que se vê na tela é o que sai impresso. Saiu de ``dicom/`` na R-58 (corte 3):
lá fica o modelo, que vai para ``rt/`` sem PIL nem matplotlib.

O desenho depende do modelo, nunca o contrário.
"""
