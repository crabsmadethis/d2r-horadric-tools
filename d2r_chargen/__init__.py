# D2R Character Generation System
from d2r_chargen.data import check_data_available
check_data_available()

from d2r_chargen.config import validate_aliases as _validate_aliases
_validate_aliases()
