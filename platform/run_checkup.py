"""Ponto de entrada do executável do checkup — o que vai para a clínica.

Existe separado do ``run_gui.py`` porque na clínica **não há Python nem o
repositório**: só chega executável. O ``tools\\checkup_clinica.bat`` continua
valendo aqui, na máquina de desenvolvimento, onde há as duas coisas.

O arquivo é fino de propósito: todo o trabalho está em
``tools/checkup_clinica.py``, que é ferramenta e continua morando com as
outras. O que ele acrescenta é o caminho de import — do fonte, ``tools/`` não
está no ``sys.path``; empacotado, o PyInstaller já pôs o módulo dentro do
pacote (ver ``CheckupClinica.spec``, que o alcança pelo ``pathex``).
"""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

from checkup_clinica import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
