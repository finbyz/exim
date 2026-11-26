# -*- coding: utf-8 -*-
from __future__ import unicode_literals

__version__ = '16.0.0'


def ensure_monkey_patches():
	"""NewV16: hooks are read from the Redis cache, so exim.hooks (which applies the
	module-level monkey patches) is not always imported in a web or job worker.
	Registered as before_request / before_job; the import runs the patches once per process."""
	import exim.hooks  # noqa: F401
