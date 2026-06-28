"""支持 ``python -m sharept_dl`` 运行。"""

import sys

from .cli import main

sys.exit(main())
