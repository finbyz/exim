# Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

"""Container No on Serial No / Batch / Serial and Batch Bundle entries.

Wraps ERPNext's serial-batch selector endpoints (see override_whitelisted_methods in
hooks.py). ERPNext reads the CSV by column position (Serial No, Batch No, Quantity),
so an extra "Container No" column at the end does not change its behaviour; we read
that column ourselves after the standard upload has run. Blank Batch No rows create
new batches when the Item has "Automatically Create New Batch" enabled.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, parse_json

from erpnext.stock.doctype.serial_and_batch_bundle import serial_and_batch_bundle as sbb

CONTAINER_HEADERS = ("container no", "container")


@frappe.whitelist()
def upload_csv_file(item_code, file_path):
	header, rows = read_csv_rows(file_path)
	is_batch_template = bool(header) and header[0] == "batch no"

	# ERPNext skips rows with a blank first column. For the batch template, a blank
	# Batch No means "create a new batch", which needs auto batch naming on the Item.
	blank_batch_rows = []
	if is_batch_template:
		blank_batch_rows = [(i, r) for i, r in enumerate(rows, start=2) if not _cell(r, 0) and flt(_cell(r, 1))]
		if blank_batch_rows and not frappe.get_cached_value("Item", item_code, "create_new_batch"):
			frappe.throw(
				_(
					"Batch No is blank in row(s) {0}. Enter the Batch No in the CSV, or enable "
					"<b>Automatically Create New Batch</b> on Item {1} so batches are created for blank rows."
				).format(", ".join(str(i) for i, _r in blank_batch_rows), frappe.bold(item_code)),
				title=_("Batch No Missing"),
			)

	result = sbb.upload_csv_file(item_code, file_path)
	serial_nos = result.get("serial_nos") or []
	batch_nos = result.get("batch_nos") or []

	container_idx = _container_index(header)
	get_container = lambda r: _cell(r, container_idx) if container_idx is not None else None  # noqa: E731

	container_map = {_cell(r, 0): get_container(r) for r in rows if _cell(r, 0) and get_container(r)}
	wanted = set(container_map.values()) | {get_container(r) for _i, r in blank_batch_rows if get_container(r)}
	valid, invalid = split_valid_containers(wanted)
	if invalid:
		frappe.msgprint(
			_("Container(s) {0} not found or not enabled. Container was left blank for those rows.").format(
				", ".join(frappe.bold(c) for c in sorted(invalid))
			),
			title=_("Unknown Container"),
			indicator="orange",
		)

	# Rows keyed by the first CSV column: Serial No when the item has serials, else Batch No.
	for row in serial_nos:
		row["container"] = _valid(container_map.get(row.get("serial_no")), valid)
	if not serial_nos:
		for row in batch_nos:
			row["container"] = _valid(container_map.get(row.get("batch_no")), valid)

	if blank_batch_rows:
		from erpnext.stock.doctype.batch.batch import make_batch

		for _i, r in blank_batch_rows:
			batch_nos.append(
				{
					"batch_no": make_batch(frappe._dict(item=item_code)),
					"qty": _cell(r, 1),
					"container": _valid(get_container(r), valid),
				}
			)
		frappe.msgprint(_("{0} new Batch(es) created").format(len(blank_batch_rows)), alert=True)

	result["serial_nos"], result["batch_nos"] = serial_nos, batch_nos
	update_masters(serial_nos, batch_nos)
	return result


@frappe.whitelist()
def add_serial_batch_ledgers(entries, child_row, doc, warehouse=None, do_not_save=False):
	if isinstance(entries, str):
		entries = parse_json(entries)

	sb_doc = sbb.add_serial_batch_ledgers(entries, child_row, doc, warehouse, bool(cint(do_not_save)))

	by_serial, by_batch = {}, {}
	for e in entries or []:
		e = frappe._dict(e)
		if not e.container:
			continue
		if e.serial_no:
			by_serial[e.serial_no] = e.container
		elif e.batch_no:
			by_batch[e.batch_no] = e.container

	if not (by_serial or by_batch):
		return sb_doc

	valid, _invalid = split_valid_containers(set(by_serial.values()) | set(by_batch.values()))

	for row in sb_doc.entries:
		container = _valid(by_serial.get(row.serial_no) or by_batch.get(row.batch_no), valid)
		if container and container != row.container:
			frappe.db.set_value("Serial and Batch Entry", row.name, "container", container, update_modified=False)
			row.container = container

	# Receiving stock: the container it came in becomes the Serial No / Batch container.
	if sb_doc.type_of_transaction == "Inward":
		update_masters(
			[{"serial_no": r.serial_no, "container": r.container} for r in sb_doc.entries if r.serial_no],
			[{"batch_no": r.batch_no, "container": r.container} for r in sb_doc.entries if r.batch_no and not r.serial_no],
		)

	return sb_doc


@frappe.whitelist()
def get_serial_batch_ledgers(item_code=None, docstatus=None, voucher_no=None, name=None, child_row=None):
	ledgers = sbb.get_serial_batch_ledgers(
		item_code=item_code, docstatus=docstatus, voucher_no=voucher_no, name=name, child_row=child_row
	)
	if not ledgers:
		return ledgers

	row_names = [d.child_row for d in ledgers if d.get("child_row")]
	containers = (
		dict(
			frappe.get_all(
				"Serial and Batch Entry",
				filters={"name": ("in", row_names)},
				fields=["name", "container"],
				as_list=True,
			)
		)
		if row_names
		else {}
	)
	for d in ledgers:
		d.container = containers.get(d.get("child_row"))

	return ledgers


def set_entry_containers(doc, method=None):
	"""Serial and Batch Bundle validate: fill blank entry containers from Serial No / Batch."""
	missing = [r for r in doc.get("entries") or [] if not r.get("container")]
	if not missing:
		return

	serials = list({r.serial_no for r in missing if r.serial_no})
	batches = list({r.batch_no for r in missing if r.batch_no})
	serial_map = _container_map("Serial No", serials)
	batch_map = _container_map("Batch", batches)

	for r in missing:
		r.container = serial_map.get(r.serial_no) or batch_map.get(r.batch_no) or None


def read_csv_rows(file_path):
	"""(lower-cased header, data rows) of the uploaded CSV; ([], []) if unreadable."""
	from frappe.core.doctype.file.utils import find_file_by_url
	from frappe.utils.csvutils import read_csv_content

	file = find_file_by_url(file_path) if file_path else None
	if not file or file.file_type != "CSV":
		return [], []

	rows = read_csv_content(file.get_content())
	if not rows:
		return [], []

	header = [str(h or "").strip().lower() for h in rows[0]]
	return header, [r for r in rows[1:] if r and any(str(c or "").strip() for c in r)]


def _container_index(header):
	return next((header.index(h) for h in CONTAINER_HEADERS if h in header), None)


def _cell(row, idx):
	if idx is None or len(row) <= idx:
		return None
	return str(row[idx] or "").strip() or None


def split_valid_containers(containers):
	containers = {c for c in containers if c}
	if not containers:
		return set(), set()
	valid = set(
		frappe.get_all("Container", filters={"name": ("in", list(containers)), "enable": 1}, pluck="name")
	)
	return valid, containers - valid


def update_masters(serial_rows, batch_rows):
	"""Set Container on Serial No / Batch. Rows: [{"serial_no"|"batch_no": ..., "container": ...}]."""
	if not (any(r.get("container") for r in serial_rows) or any(r.get("container") for r in batch_rows)):
		return

	frappe.has_permission("Serial and Batch Bundle", "write", throw=True)

	for doctype, key, rows in (("Serial No", "serial_no", serial_rows), ("Batch", "batch_no", batch_rows)):
		for r in rows:
			if r.get(key) and r.get("container") and frappe.db.exists(doctype, r[key]):
				frappe.db.set_value(doctype, r[key], "container", r["container"], update_modified=False)


def _container_map(doctype, names):
	if not names:
		return {}
	return dict(
		frappe.get_all(
			doctype, filters={"name": ("in", names), "container": ("is", "set")}, fields=["name", "container"], as_list=True
		)
	)


def _valid(container, valid):
	return container if container in valid else None
