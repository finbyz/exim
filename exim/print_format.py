from __future__ import unicode_literals

import os
import tempfile

import frappe
import pdfkit
from PyPDF2 import PdfFileReader

from frappe import _
from frappe.utils import scrub_urls
from frappe.utils.pdf import cleanup, read_options_from_html


SAFE_PDFKIT_OPTIONS = {
	"print-media-type",
	"background",
	"images",
	"quiet",
	"encoding",
	"margin-right",
	"margin-left",
	"margin-top",
	"margin-bottom",
	"page-size",
	"orientation",
	"title",
	"disable-javascript",
	"no-stop-slow-scripts",
}


def append_pdf(input, output):
	# Merging multiple pdf files
	for page_num in range(input.numPages):
		output.addPage(input.getPage(page_num))


@frappe.whitelist()
def download_pdf(doctype, name, format=None, doc=None, no_letterhead=0):
	html = frappe.get_print(
		doctype,
		name,
		format,
		doc=doc,
		no_letterhead=no_letterhead
	)

	frappe.local.response.filename = (
		name.replace(" ", "-").replace("/", "-") + ".pdf"
	)

	frappe.local.response.filecontent = get_pdf(html)
	frappe.local.response.type = "pdf"


def get_pdf(html, options=None, output=None):
	html = scrub_urls(html)
	html, options = prepare_options(html, options)

	filedata = None
	tmp_dir = tempfile.gettempdir()

	with tempfile.NamedTemporaryFile(
		suffix=".pdf",
		prefix="frappe-pdf-",
		delete=False,
		dir=tmp_dir
	) as tmpfile:
		fname = tmpfile.name

	# Defense-in-depth:
	# Ensure generated file stays within the OS temp directory
	resolved_path = os.path.realpath(fname)
	resolved_tmp_dir = os.path.realpath(tmp_dir)

	if not resolved_path.startswith(resolved_tmp_dir + os.sep):
		raise RuntimeError(
			"Unexpected temp file path detected during PDF generation"
		)

	try:
		pdfkit.from_string(html, fname, options=options or {})

		if output:
			with open(fname, "rb") as pdf_file:  # nosec B108
				append_pdf(PdfFileReader(pdf_file), output)
		else:
			with open(fname, "rb") as pdf_file:  # nosec B108
				filedata = pdf_file.read()

	except IOError as e:
		error_message = str(e)

		if (
			"ContentNotFoundError" in error_message
			or "ContentOperationNotPermittedError" in error_message
			or "UnknownContentError" in error_message
			or "RemoteHostClosedError" in error_message
		):

			if os.path.isfile(fname):
				with open(fname, "rb") as pdf_file:  # nosec B108
					filedata = pdf_file.read()
			else:
				frappe.throw(
					_("PDF generation failed because of broken image links")
				)
		else:
			raise

	finally:
		cleanup(fname, options)

		if os.path.isfile(fname):
			os.remove(fname)

	if output:
		return output

	return filedata


def prepare_options(html, options):
	if not options:
		options = {}

	options.update({
		"print-media-type": None,
		"background": None,
		"images": None,
		"quiet": None,
		"encoding": "UTF-8",
		"margin-right": "2mm",
		"margin-left": "2mm",
		"disable-javascript": None,
	})

	html, html_options = read_options_from_html(html)

	# Only allow explicitly approved wkhtmltopdf options
	if html_options:
		safe_html_options = {
			key: value
			for key, value in html_options.items()
			if key in SAFE_PDFKIT_OPTIONS
		}

		options.update(safe_html_options)

	# cookies
	if frappe.session and frappe.session.sid:
		options["cookie"] = [("sid", frappe.session.sid)]

	# page size
	if not options.get("page-size"):
		options["page-size"] = (
			frappe.db.get_single_value(
				"Print Settings",
				"pdf_page_size"
			) or "A4"
		)

	return html, options