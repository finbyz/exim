from __future__ import unicode_literals

import os
import tempfile
import pdfkit
import frappe

from frappe.utils import scrub_urls
from frappe import _
from PyPDF2 import PdfFileReader
from frappe.utils.pdf import cleanup, read_options_from_html

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

	with tempfile.NamedTemporaryFile(
		suffix=".pdf",
		prefix="frappe-pdf-",
		delete=False
	) as tmpfile:

		fname = tmpfile.name

	try:
		pdfkit.from_string(html, fname, options=options or {})

		if output:
			with open(fname, "rb") as pdf_file:
				append_pdf(PdfFileReader(pdf_file), output)
		else:
			with open(fname, "rb") as pdf_file:
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
				with open(fname, "rb") as pdf_file:
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
		'print-media-type': None,
		'background': None,
		'images': None,
		'quiet': None,
		'encoding': "UTF-8",
		'margin-right': '2mm',
		'margin-left': '2mm'
	})

	html, html_options = read_options_from_html(html)
	options.update(html_options or {})

	# cookies
	if frappe.session and frappe.session.sid:
		options['cookie'] = [('sid', frappe.session.sid)]

	# page size
	if not options.get("page-size"):
		options['page-size'] = (
			frappe.db.get_single_value(
				"Print Settings",
				"pdf_page_size"
			) or "A4"
		)

	return html, options