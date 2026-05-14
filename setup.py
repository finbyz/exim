# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

import ast
import os
import re

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

requirements_path = os.path.join(BASE_DIR, "requirements.txt")
init_path = os.path.join(BASE_DIR, "exim", "__init__.py")

with open(requirements_path, encoding="utf-8") as f:
	install_requires = f.read().strip().split("\n")

_version_re = re.compile(r"__version__\s+=\s+(.*)")

with open(init_path, encoding="utf-8") as f:
	version = str(
		ast.literal_eval(
			_version_re.search(f.read()).group(1)
		)
	)

setup(
	name="exim",
	version=version,
	description="custom app for exim module",
	author="FinByz Tech Pvt Ltd",
	author_email="info@finbyz.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)