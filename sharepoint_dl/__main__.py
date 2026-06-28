"""支持 ``python -m sharepoint_dl`` 运行。"""

import sys

from .cli import main

sys.exit(main())
