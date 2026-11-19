# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

"""Print the actual attached files of an Import Shipment.

Files = Draft / Final Document of each Required Documents row, then any other file in the
shipment's attachments (sidebar), without duplicates.

- Print format preview (HTML): `get_attachment_pages(doc)` (Jinja) renders each page of attached
  PDFs and images as a standalone page for clean preview and browser printing.
- PDF Download: `custom_download_pdf` overrides frappe.utils.print_format.download_pdf so clicking
  "PDF" returns the merged PDF directly, containing all attached PDF pages and images.
"""

import hashlib
import io
import os
import re
import urllib.parse

import frappe
from frappe import _
from frappe.utils import cint, flt

PDF_GENERATOR = "Attachments"
MARKER_RE = re.compile(r'data-exim-attachments="([^"]+)"')
IMAGE_EXT = ("png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff")
A4_WIDTH_INCH = 8.27


def _ext(url):
	return (url or "").split("?")[0].rsplit(".", 1)[-1].lower()


def _kind(url):
	ext = _ext(url)
	if ext == "pdf":
		return "pdf"
	if ext in IMAGE_EXT:
		return "image"
	return "other"


def get_attachment_urls(doc):
	urls = []
	for row in doc.get("required_documents") or []:
		for url in (row.get("attachment"), row.get("final_document")):
			if url and url not in urls:
				urls.append(url)

	for url in frappe.get_all(
		"File",
		filters={"attached_to_doctype": doc.doctype, "attached_to_name": doc.name, "is_folder": 0},
		order_by="creation asc",
		pluck="file_url",
	):
		if url and url not in urls:
			urls.append(url)
	return urls


def get_attachment_files(doc):
	"""Jinja (print format): [{"url", "kind": pdf|image|other, "file_name"}] of the shipment's files."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Import Shipment", doc)
	return [
		{"url": url, "kind": _kind(url), "file_name": url.rsplit("/", 1)[-1]} for url in get_attachment_urls(doc)
	]


def get_attachment_pages(doc):
	"""Jinja helper returning list of pages across all PDF and image attachments."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Import Shipment", doc)

	import pypdfium2

	pages = []
	for url in get_attachment_urls(doc):
		kind = _kind(url)
		file_name = url.rsplit("/", 1)[-1]
		if kind == "image":
			pages.append({
				"kind": "image",
				"src": url,
				"page_no": 1,
				"total_pages": 1,
				"file_name": file_name,
				"attachment_url": url,
			})
		elif kind == "pdf":
			try:
				content = _get_content(url)
				pdf = pypdfium2.PdfDocument(content)
				num_pages = len(pdf)
				for p in range(1, num_pages + 1):
					pages.append({
						"kind": "pdf_page",
						"src": f"/api/method/exim.exim.utils.shipment_attachments.get_pdf_page_image?url={urllib.parse.quote(url)}&page={p}",
						"page_no": p,
						"total_pages": num_pages,
						"file_name": file_name,
						"attachment_url": url,
					})
			except Exception as e:
				frappe.log_error(title=f"Could not load PDF pages for {url}: {e}")
	return pages


@frappe.whitelist()
def get_pdf_page_image(url, page=1, scale=1.5):
	"""Renders a single page of a PDF attachment as JPEG image for print preview."""
	import pypdfium2

	page_num = cint(page)
	if page_num < 1:
		page_num = 1

	scale_val = flt(scale) or 1.5
	scale_val = max(1.0, min(3.0, scale_val))

	cache_key = hashlib.sha256(f"{url}_{page_num}_{scale_val}".encode()).hexdigest()
	cache_dir = frappe.get_site_path("private", "cache", "pdf_pages")
	os.makedirs(cache_dir, exist_ok=True)
	cache_file = os.path.join(cache_dir, f"{cache_key}.jpg")

	if os.path.exists(cache_file):
		with open(cache_file, "rb") as f:
			content = f.read()
	else:
		pdf_bytes = _get_content(url)
		pdf = pypdfium2.PdfDocument(pdf_bytes)
		if page_num > len(pdf):
			frappe.throw(_("Page {0} out of range (total pages: {1})").format(page_num, len(pdf)))

		pdf_page = pdf[page_num - 1]
		pil_image = pdf_page.render(scale=scale_val).to_pil()
		pil_image.save(cache_file, format="JPEG", quality=85, optimize=True)
		with open(cache_file, "rb") as f:
			content = f.read()

	frappe.local.response.filename = f"page_{page_num}.jpg"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"
	frappe.local.response.display_content_as = "inline"
	frappe.local.response.content_type = "image/jpeg"
	frappe.local.response.headers = {
		"Cache-Control": "public, max-age=86400",
	}


def build_attachments_pdf(doc):
	"""(pdf bytes or None, skipped urls)"""
	from pypdf import PdfReader, PdfWriter

	writer = PdfWriter()
	skipped = []
	for url in get_attachment_urls(doc):
		kind = _kind(url)
		try:
			if kind == "pdf":
				reader = PdfReader(io.BytesIO(_get_content(url)))
				if reader.is_encrypted:
					reader.decrypt("")
				for page in reader.pages:
					writer.add_page(page)
			elif kind == "image":
				for page in PdfReader(io.BytesIO(_image_to_pdf(_get_content(url)))).pages:
					writer.add_page(page)
			else:
				skipped.append(url)
		except Exception:
			skipped.append(url)
			frappe.log_error(title=f"Print Attachments: could not add {url} ({doc.name})")

	if not len(writer.pages):
		return None, skipped

	out = io.BytesIO()
	writer.write(out)
	return out.getvalue(), skipped


def set_attachments_pdf_generator(doc, method=None):
	"""Print Format validate: a format with the attachments marker must use the "Attachments"
	PDF generator, otherwise its PDF would be the (empty) HTML instead of the attached files."""
	if "data-exim-attachments" in (doc.get("html") or ""):
		doc.pdf_generator = PDF_GENERATOR


def attachments_pdf_generator(print_format, html, options, output, pdf_generator):
	"""pdf_generator hook: PDF made only of the attached files, for print formats using "Attachments"."""
	if pdf_generator != PDF_GENERATOR:
		return None

	doctype = frappe.get_cached_value("Print Format", print_format, "doc_type") or "Import Shipment"
	names = list(dict.fromkeys(MARKER_RE.findall(html or ""))) or [frappe.form_dict.get("name")]

	from pypdf import PdfReader, PdfWriter

	writer = PdfWriter()
	for name in filter(None, names):
		doc = frappe.get_doc(doctype, name)
		doc.check_permission("read")
		pdf, _skipped = build_attachments_pdf(doc)
		if pdf:
			for page in PdfReader(io.BytesIO(pdf)).pages:
				writer.add_page(page)

	if not len(writer.pages):
		frappe.throw(
			_("No PDF or image attachments to print for {0}.").format(", ".join(filter(None, names))),
			title=_("Nothing to Print"),
		)

	buf = io.BytesIO()
	writer.write(buf)
	return buf.getvalue()


@frappe.whitelist()
def download_attachments_pdf(name):
	"""Print Attachments button on Import Shipment."""
	doc = frappe.get_doc("Import Shipment", name)
	doc.check_permission("read")

	pdf, _skipped = build_attachments_pdf(doc)
	if not pdf:
		frappe.throw(
			_("No PDF or image attachments to print for {0}.").format(frappe.bold(name)),
			title=_("Nothing to Print"),
		)

	frappe.local.response.filename = f"{name}-attachments.pdf"
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"


@frappe.whitelist()
def custom_download_pdf(
	doctype: str,
	name: str,
	format: str | None = None,
	doc=None,
	no_letterhead: bool | int = 0,
	language: str | None = None,
	letterhead: str | None = None,
	pdf_generator: str | None = None,
	**kwargs,
):
	"""Override for frappe.utils.print_format.download_pdf to serve merged attachments PDF."""
	format_name = format or frappe.form_dict.get("format")
	is_attachments_format = False

	if format_name:
		if format_name == "Required Document Attachments" or "Attachments" in format_name:
			is_attachments_format = True
		elif frappe.db.exists("Print Format", format_name):
			pf_html = frappe.db.get_value("Print Format", format_name, "html") or ""
			if "data-exim-attachments" in pf_html:
				is_attachments_format = True

	if is_attachments_format and doctype == "Import Shipment":
		doc = doc or frappe.get_doc(doctype, name)
		doc.check_permission("read")

		pdf, skipped = build_attachments_pdf(doc)
		if not pdf:
			frappe.throw(
				_("No PDF or image attachments to print for {0}.").format(frappe.bold(name)),
				title=_("Nothing to Print"),
			)

		frappe.local.response.filename = f"{name}.pdf"
		frappe.local.response.filecontent = pdf
		frappe.local.response.type = "pdf"
		return

	from frappe.utils.print_format import download_pdf as standard_download_pdf

	return standard_download_pdf(
		doctype=doctype,
		name=name,
		format=format,
		doc=doc,
		no_letterhead=no_letterhead,
		language=language,
		letterhead=letterhead,
		pdf_generator=pdf_generator,
	)


def _get_content(url):
	from frappe.core.doctype.file.utils import find_file_by_url

	# returns the File only when the user is allowed to read it
	file = find_file_by_url(url)
	if not file:
		raise frappe.PermissionError(url)
	content = file.get_content()
	return content.encode() if isinstance(content, str) else content


def _image_to_pdf(content):
	from PIL import Image, ImageOps

	img = ImageOps.exif_transpose(Image.open(io.BytesIO(content)))
	if img.mode != "RGB":
		img = img.convert("RGB")
	# DPI chosen so the page is at most A4 width
	dpi = max(72.0, img.width / A4_WIDTH_INCH)
	buf = io.BytesIO()
	img.save(buf, format="PDF", resolution=dpi)
	return buf.getvalue()
