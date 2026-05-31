"""把项目根加入 sys.path，让 `import backend.app...` 在 pytest 下可用。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
