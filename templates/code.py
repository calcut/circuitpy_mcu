# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT
import supervisor

code = '/path_to/desired_code.py'

supervisor.disable_autoreload()
supervisor.set_next_code_file(code, reload_on_success=False)
supervisor.reload()