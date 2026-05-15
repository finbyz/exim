# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

import ast
import os
import re

BASE_DIR = os.path.realpath(os.path.dirname(__file__))

def safe_project_path(*parts):
	"""
	Resolve a project-relative path and ensure it
	stays inside the project root directory.
	"""
	target = os.path.realpath(os.path.join(BASE_DIR, *parts))

	if not target.startswith(BASE_DIR + os.sep):
		raise ValueError(f"Path traversal detected: {target}")

	return target

requirements_path = safe_project_path("requirements.txt")
init_path = safe_project_path("exim", "__init__.py")

# Optional integrity checks
for path, label in [
	(requirements_path, "requirements.txt"),
	(init_path, "exim/__init__.py"),
]:
	if not os.path.isfile(path):
		raise FileNotFoundError(f"Expected project file not found: {label}")

with open(requirements_path, encoding="utf-8") as f:
	install_requires = f.read().strip().split("\n")

_version_re = re.compile(r"__version__\s+=\s+(.*)")

with open(init_path, encoding="utf-8") as f:
	match = _version_re.search(f.read())

	if not match:
		raise ValueError("Unable to determine package version")

	version = str(ast.literal_eval(match.group(1)))

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