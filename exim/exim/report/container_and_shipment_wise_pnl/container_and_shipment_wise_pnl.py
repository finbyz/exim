# Copyright (c) 2026, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

"""Container wise and Shipment wise Profit & Loss for Import Shipments.

Cost of a container
	Purchase: Purchase Receipt / Purchase Invoice (update stock) batch rows whose Container is one of the
	shipment's containers, valued at the item's net rate (company currency).
	Expenses: the shipment's Charges (actual amount, or the estimated amount while no actual is booked),
	divided equally by the number of containers.

Income of a container
	Every batch received in the container is followed until it is consumed. External sales (Sales Invoice
	with Update Stock, Delivery Note) are income at the net rate, returns reduce it. An inter-company sale is
	not income: it is a transfer, and the batch is followed into the other company (same batch, or the batch
	on the linked inter-company Purchase Receipt / Purchase Invoice row) until it is sold outside the group.

Profit / Loss = Sales Value + Balance Stock Value (unsold qty at landed cost) - Total Cost.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

SALE_ITEM = {"Sales Invoice": "Sales Invoice Item", "Delivery Note": "Delivery Note Item"}
PURCHASE_ITEM = {"Purchase Receipt": "Purchase Receipt Item", "Purchase Invoice": "Purchase Invoice Item"}
# Inter-company sale row -> receiving purchase row field that points back to it
RECEIVING_SIDE = {
	"Delivery Note": ("Purchase Receipt Item", "delivery_note_item"),
	"Sales Invoice": ("Purchase Invoice Item", "sales_invoice_item"),
}
AMOUNT_FIELDS = (
	"purchase_qty",
	"purchase_value",
	"expenses",
	"total_cost",
	"sold_qty",
	"sales_value",
	"other_out_qty",
	"transfer_qty",
	"moved_qty",
	"moved_cost",
	"balance_qty",
	"balance_value",
	"profit",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	currency = get_currency(filters)
	shipments = get_shipments(filters)
	containers = get_containers(shipments)
	track_batches(containers)
	finalise(containers)

	if filters.container:
		containers = [c for c in containers if c.container == filters.container]

	entities = get_entities(shipments, containers, filters)
	if not entities:
		return get_columns(currency), []

	return (
		get_columns(currency),
		get_data(entities, filters),
		None,
		get_chart(entities),
		get_report_summary(entities, currency),
	)


# ---------------------------------------------------------------- shipments


def get_shipments(filters):
	conditions = {"status": ("!=", "Cancelled")}
	if filters.company:
		conditions["company"] = filters.company
	names = None
	if filters.container:
		# only the shipments that carried this container
		names = set(
			frappe.get_all(
				"Import Shipment Container Details",
				filters={"container": filters.container, "parenttype": "Import Shipment"},
				pluck="parent",
				distinct=True,
			)
		)
	if filters.import_shipment:
		names = {filters.import_shipment} if names is None else names & {filters.import_shipment}
	if names is not None:
		conditions["name"] = ("in", list(names) or [""])

	rows = frappe.get_list(
		"Import Shipment",
		filters=conditions,
		fields=["name", "shipment_no", "company", "shipper", "status", "eta", "creation", "container_nos"],
		order_by="creation asc",
	)

	from_date = getdate(filters.from_date) if filters.from_date else None
	to_date = getdate(filters.to_date) if filters.to_date else None
	out = []
	for s in rows:
		# Shipment date: ETA, or the date it was created when ETA is blank
		s.shipment_date = getdate(s.eta or s.creation)
		if from_date and s.shipment_date < from_date:
			continue
		if to_date and s.shipment_date > to_date:
			continue
		out.append(s)
	return out


def get_containers(shipments):
	"""One record per (shipment, container), with its share of the shipment expenses
	and the purchase rows received in it."""
	if not shipments:
		return []

	names = [s.name for s in shipments]
	by_name = {s.name: s for s in shipments}

	container_rows = frappe.get_all(
		"Import Shipment Container Details",
		filters={"parent": ("in", names), "parenttype": "Import Shipment", "container": ("is", "set")},
		fields=["parent", "container", "item_code"],
		order_by="parent, idx",
	)
	item_rows = frappe.get_all(
		"Import Shipment Item",
		filters={"parent": ("in", names), "parenttype": "Import Shipment"},
		fields=["parent", "product"],
	)
	charge_rows = frappe.get_all(
		"Import Shipment Charge",
		filters={"parent": ("in", names), "parenttype": "Import Shipment"},
		fields=["parent", "charge_type", "item_name", "amount", "actual_amount"],
		order_by="parent, idx",
	)

	for s in shipments:
		s.containers, s.item_codes, s.expenses, s.charges = [], set(), 0.0, defaultdict(float)
		s.has_actual = s.has_estimate = False
	for r in container_rows:
		s = by_name[r.parent]
		if r.container not in s.containers:
			s.containers.append(r.container)
		if r.item_code:
			s.item_codes.add(r.item_code)
	for r in item_rows:
		if r.product:
			by_name[r.parent].item_codes.add(r.product)
	for r in charge_rows:
		s = by_name[r.parent]
		# Actual amount once the expense bill is booked, the estimate until then
		name = r.charge_type or r.item_name or _("Other Charges")
		if flt(r.actual_amount):
			s.expenses += flt(r.actual_amount)
			s.charges[name] += flt(r.actual_amount)
			s.has_actual = True
		elif flt(r.amount):
			s.expenses += flt(r.amount)
			s.charges[_("{0} (Estimated)").format(name)] += flt(r.amount)
			s.has_estimate = True

	containers = []
	for s in shipments:
		n = len(s.containers)
		share = s.expenses / n if n else 0.0
		for c in s.containers:
			containers.append(
				frappe._dict(
					key=(s.name, c),
					shipment=s.name,
					container=c,
					shipment_date=s.shipment_date,
					item_codes=s.item_codes,
					expenses=share,
					charges={k: v / n for k, v in s.charges.items()},
					batches=defaultdict(new_batch_stats),
				)
			)
	return containers


def new_batch_stats():
	return frappe._dict(item_code=None, source_batch=None, **{f: 0.0 for f in AMOUNT_FIELDS})


# ---------------------------------------------------------------- batch tracking


def get_bundle_entries(container_names=None, batch_nos=None):
	conditions = ["sb.docstatus = 1", "sb.is_cancelled = 0", "ifnull(e.batch_no, '') != ''"]
	values = {}
	if container_names is not None:
		conditions.append("sb.voucher_type in ('Purchase Receipt', 'Purchase Invoice')")
		conditions.append("sb.is_rejected = 0")
		conditions.append("e.container in %(containers)s")
		values["containers"] = tuple(container_names)
	if batch_nos is not None:
		conditions.append("e.batch_no in %(batches)s")
		values["batches"] = tuple(batch_nos)

	return frappe.db.sql(
		f"""
		select e.name as entry, e.batch_no, e.container, e.qty, sb.item_code, sb.company,
			sb.voucher_type, sb.voucher_no, sb.voucher_detail_no, sb.is_rejected
		from `tabSerial and Batch Entry` e
		inner join `tabSerial and Batch Bundle` sb on sb.name = e.parent
		where {" and ".join(conditions)}
		order by sb.posting_datetime, sb.creation
		""",
		values,
		as_dict=True,
	)


class VoucherCache:
	"""Item rows (net rate) and headers (internal flag, return flag) of the vouchers seen while tracking."""

	def __init__(self):
		self.items, self.headers = {}, {}
		self.companies = set(frappe.get_all("Company", pluck="name"))

	def load(self, entries):
		wanted_items, wanted_headers = defaultdict(set), defaultdict(set)
		for e in entries:
			child = SALE_ITEM.get(e.voucher_type) or PURCHASE_ITEM.get(e.voucher_type)
			if not child:
				continue
			if e.voucher_detail_no and (child, e.voucher_detail_no) not in self.items:
				wanted_items[child].add(e.voucher_detail_no)
			if (e.voucher_type, e.voucher_no) not in self.headers:
				wanted_headers[e.voucher_type].add(e.voucher_no)

		for child, names in wanted_items.items():
			for r in frappe.get_all(
				child, filters={"name": ("in", list(names))}, fields=["name", "base_net_rate", "item_code"]
			):
				self.items[(child, r.name)] = r

		for doctype, names in wanted_headers.items():
			sale = doctype in SALE_ITEM
			party = "customer" if sale else "supplier"
			internal = "is_internal_customer" if sale else "is_internal_supplier"
			for r in frappe.get_all(
				doctype,
				filters={"name": ("in", list(names))},
				fields=["name", "is_return", "represents_company", internal + " as is_internal", party + " as party"],
			):
				r.is_internal = bool(
					r.is_internal or r.represents_company or (r.party and r.party in self.companies)
				)
				self.headers[(doctype, r.name)] = r

	def rate(self, e):
		child = SALE_ITEM.get(e.voucher_type) or PURCHASE_ITEM.get(e.voucher_type)
		row = self.items.get((child, e.voucher_detail_no))
		return flt(row.base_net_rate) if row else 0.0

	def header(self, e):
		return self.headers.get((e.voucher_type, e.voucher_no)) or frappe._dict()


def track_batches(containers):
	if not containers:
		return

	cache = VoucherCache()
	by_container = defaultdict(list)
	for c in containers:
		by_container[c.container].append(c)

	# 1. Purchases received in the shipment containers
	purchase_entries = get_bundle_entries(container_names=list(by_container))
	cache.load(purchase_entries)

	owner = {}  # batch_no -> container record the batch belongs to
	counted = set()  # bundle entries already used
	for e in purchase_entries:
		if cache.header(e).is_internal:
			continue  # an inter-company receipt is a transfer, not a purchase
		c = pick_container(by_container[e.container], e)
		if not c:
			continue
		add_purchase(c, e, cache)
		counted.add(e.entry)
		owner.setdefault(e.batch_no, c)

	# 2. Follow every batch until it is consumed, across inter-company transfers
	pending = set(owner)
	while pending:
		entries = [e for e in get_bundle_entries(batch_nos=list(pending)) if e.entry not in counted]
		cache.load(entries)
		pending = set()
		# inter-company sale row -> {"c": container, "out": {source batch: qty sent}}
		internal_sales = defaultdict(dict)

		for e in entries:
			counted.add(e.entry)
			c = owner.get(e.batch_no)
			if not c:
				continue
			stats = c.batches[e.batch_no]
			stats.item_code = stats.item_code or e.item_code
			head = cache.header(e)
			qty = flt(e.qty)  # inward +, outward -

			if e.voucher_type in SALE_ITEM:
				if head.is_internal:
					stats.transfer_qty -= qty
					if e.voucher_detail_no:
						src = internal_sales[e.voucher_type].setdefault(
							e.voucher_detail_no, {"c": c, "out": defaultdict(float)}
						)
						src["out"][e.batch_no] -= qty
				else:
					stats.sold_qty -= qty
					stats.sales_value -= qty * cache.rate(e)
			elif e.voucher_type in PURCHASE_ITEM:
				# Purchase returns of the original receipt adjust the purchase.
				# Inter-company receipts and other receipts of an already tracked batch are transfers in.
				if head.is_return and not head.is_internal and not e.is_rejected:
					add_purchase(c, e, cache)
			else:
				# Stock Entry, Stock Reconciliation, etc.: wastage, consumption or adjustment
				stats.other_out_qty -= qty

		# 3. Batches received by the other company against an inter-company sale
		for doctype, source in internal_sales.items():
			for row, batch_no, qty in get_received_batches(doctype, list(source)):
				src = source[row]
				c, out = src["c"], src["out"]
				if batch_no in out:
					continue  # same batch carried over: it is already being followed
				move_batch_qty(c, out, batch_no, qty)
				if batch_no not in owner:
					owner[batch_no] = c
					pending.add(batch_no)


def get_received_batches(doctype, source_rows):
	"""(source sale row, batch, qty) received by the other company against inter-company sale rows."""
	child, link_field = RECEIVING_SIDE[doctype]
	received = frappe.get_all(
		child,
		filters={link_field: ("in", source_rows), "docstatus": 1},
		fields=[link_field + " as source_row", "serial_and_batch_bundle", "batch_no", "stock_qty"],
	)
	out = [(r.source_row, r.batch_no, flt(r.stock_qty)) for r in received if r.batch_no and not r.serial_and_batch_bundle]
	bundles = {r.serial_and_batch_bundle: r.source_row for r in received if r.serial_and_batch_bundle}
	if bundles:
		for r in frappe.get_all(
			"Serial and Batch Entry",
			filters={"parent": ("in", list(bundles)), "batch_no": ("is", "set")},
			fields=["parent", "batch_no", "qty"],
		):
			out.append((bundles[r.parent], r.batch_no, abs(flt(r.qty))))
	return out


def move_batch_qty(c, out, new_batch, qty):
	"""The other company received the stock under a new batch: move the qty from the source batch(es)
	to the new batch, so the new batch's sales and balance are valued at the source batch's cost."""
	total_out = sum(out.values())
	if not total_out or not qty:
		return
	target = c.batches[new_batch]
	for batch_no, sent in out.items():
		share = qty * sent / total_out
		c.batches[batch_no].moved_qty += share
		target.moved_qty -= share
	target.source_batch = target.source_batch or max(out, key=out.get)


def pick_container(candidates, e):
	"""The shipment container a purchase row belongs to. The Container on the batch decides it. Only when the
	same container number is on more than one shipment: prefer shipments that list the item, then the
	latest shipment dated on or before the receipt."""
	if len(candidates) <= 1:
		return candidates[0] if candidates else None

	matches = [c for c in candidates if e.item_code in c.item_codes] or candidates
	if len(matches) == 1:
		return matches[0]

	posting_date = getdate(
		frappe.db.get_value(e.voucher_type, e.voucher_no, "posting_date") or matches[-1].shipment_date
	)
	earlier = [c for c in matches if c.shipment_date <= posting_date]
	return (earlier or matches)[-1]


def add_purchase(c, e, cache):
	stats = c.batches[e.batch_no]
	stats.item_code = stats.item_code or e.item_code
	stats.purchase_qty += flt(e.qty)
	stats.purchase_value += flt(e.qty) * cache.rate(e)


# ---------------------------------------------------------------- totals


def finalise(containers):
	"""Share container expenses over its batches (by purchase value, else qty) and work out the P&L."""
	for c in containers:
		batches = c.batches
		base_value = sum(flt(b.purchase_value) for b in batches.values())
		base_qty = sum(flt(b.purchase_qty) for b in batches.values())
		for b in batches.values():
			if base_value:
				b.expenses = c.expenses * flt(b.purchase_value) / base_value
			elif base_qty:
				b.expenses = c.expenses * flt(b.purchase_qty) / base_qty

		# Purchased batches first, then batches received inter-company at their source batch's cost
		for b in sorted(batches.values(), key=lambda b: bool(b.source_batch)):
			unit_cost = None
			if b.source_batch and not flt(b.purchase_qty):
				unit_cost = flt(batches[b.source_batch].get("unit_cost"))
			set_pnl(b, unit_cost=unit_cost)

		totals = frappe._dict({f: sum(flt(b.get(f)) for b in batches.values()) for f in AMOUNT_FIELDS})
		if not batches:
			totals.expenses = c.expenses  # expenses with nothing received yet
		set_pnl(totals, recompute_balance_value=False)
		c.update(totals)


def set_pnl(row, recompute_balance_value=True, unit_cost=None):
	"""Batch rows (recompute_balance_value) work out their landed unit cost; qty moved to another batch
	inter-company takes its cost with it (moved_cost). Container / shipment rows only add up their batches."""
	landed = flt(row.purchase_value) + flt(row.expenses)
	row.balance_qty = flt(row.purchase_qty) - flt(row.sold_qty) - flt(row.other_out_qty) - flt(row.moved_qty)
	if recompute_balance_value:
		if unit_cost is None:
			unit_cost = landed / flt(row.purchase_qty) if flt(row.purchase_qty) else 0.0
		row.unit_cost = unit_cost
		row.moved_cost = unit_cost * flt(row.moved_qty)
		row.balance_value = unit_cost * row.balance_qty if row.balance_qty > 0 else 0.0
	row.total_cost = landed - flt(row.moved_cost)
	row.profit = flt(row.sales_value) + flt(row.balance_value) - row.total_cost
	row.profit_pct = row.profit / row.total_cost * 100 if row.total_cost else 0.0
	row.status = status_of(row)


def status_of(row):
	if not flt(row.purchase_qty) and flt(row.moved_qty) >= 0:
		return _("Not Received")
	if flt(row.balance_qty) <= 0:
		return _("Closed")
	if flt(row.sold_qty) or flt(row.other_out_qty):
		return _("Partly Sold")
	return _("In Stock")


def sum_rows(rows):
	total = frappe._dict({f: sum(flt(r.get(f)) for r in rows) for f in AMOUNT_FIELDS})
	set_pnl(total, recompute_balance_value=False)
	return total




# ---------------------------------------------------------------- output
# T format, like a Trading / P&L account: Expenses on the left, Income on the right, one block per
# container (Container Wise) or per shipment (Shipment Wise), and a combined block when there are several.
# Net Profit sits on the Expenses side and Net Loss on the Income side, so both sides add up to the same total.

TOTAL_FIELDS = (
	"purchase_value",
	"expenses",
	"total_cost",
	"sales_value",
	"balance_value",
	"total_income",
	"profit",
	"purchase_qty",
	"sold_qty",
	"other_out_qty",
	"balance_qty",
)


def get_entities(shipments, containers, filters):
	"""The report blocks. Each one adds up one or more container records."""
	by_shipment = defaultdict(list)
	for c in containers:
		by_shipment[c.shipment].append(c)

	entities = []
	if filters.get("view") == "Shipment Wise":
		for s in shipments:
			rows = by_shipment.get(s.name) or []
			if not rows and filters.container:
				continue  # filtered on a container this shipment did not carry
			# every shipment is shown, even with no containers or costs booked yet
			title = _("Shipment: {0} ({1} Container(s))").format(s.name, len(s.containers))
			if filters.container:
				title = _("Shipment: {0} (showing Container {1} of {2})").format(
					s.name, filters.container, len(s.containers)
				)
			entities.append(make_entity(s.name, title, rows, None if rows else dict(s.charges)))
	else:
		for c in containers:
			title = _("Container: {0} (Shipment: {1})").format(c.container, c.shipment)
			entities.append(make_entity(c.container, title, [c]))
	return entities


def make_entity(label, title, containers, charges=None):
	e = frappe._dict(label=label, title=title, purchase=defaultdict(float), sales=defaultdict(float))
	e.charges = defaultdict(float, charges or {})
	# item -> [(batch label, qty, value)] for Show Batches
	e.purchase_batches, e.sales_batches = defaultdict(list), defaultdict(list)
	for c in containers:
		if charges is None:
			for name, amount in c.charges.items():
				e.charges[name] += amount
		for batch_no, b in sorted(c.batches.items()):
			item = b.item_code or _("Unknown Item")
			batch = _("{0} (from {1})").format(batch_no, b.source_batch) if b.source_batch else batch_no
			if flt(b.purchase_value):
				e.purchase[item] += flt(b.purchase_value)
				e.purchase_batches[item].append((batch, b.purchase_qty, b.purchase_value))
			if flt(b.sales_value):
				e.sales[item] += flt(b.sales_value)
				e.sales_batches[item].append((batch, b.sold_qty, b.sales_value))

	totals = sum_rows(containers)
	totals.expenses = sum(e.charges.values())
	set_totals(totals)
	e.totals = totals
	return e


def set_totals(t):
	t.total_cost = flt(t.purchase_value) + flt(t.expenses)
	t.total_income = flt(t.sales_value) + flt(t.balance_value)
	t.profit = t.total_income - t.total_cost
	t.profit_pct = t.profit / t.total_cost * 100 if t.total_cost else 0.0


def combine(entities, title):
	e = frappe._dict(label=_("Total"), title=title, purchase_batches={}, sales_batches={})
	for attr in ("purchase", "sales", "charges"):
		e[attr] = defaultdict(float)
		for x in entities:
			for k, v in x[attr].items():
				e[attr][k] += v
	e.totals = frappe._dict({f: sum(flt(x.totals.get(f)) for x in entities) for f in TOTAL_FIELDS})
	set_totals(e.totals)
	return e


def get_data(entities, filters):
	items = list({i for e in entities for i in (*e.purchase, *e.sales)})
	item_names = (
		dict(frappe.get_all("Item", filters={"name": ("in", items)}, fields=["name", "item_name"], as_list=True))
		if items
		else {}
	)

	blocks = list(entities)
	if len(entities) > 1:
		what = _("Shipments") if filters.get("view") == "Shipment Wise" else _("Containers")
		blocks.append(combine(entities, _("Total of {0} {1}").format(len(entities), what)))

	data = []
	for i, e in enumerate(blocks):
		if i:
			data.append(frappe._dict(row_type="gap"))
		data += t_block(e, item_names, filters.get("show_batches"))
	return data


def t_block(e, item_names, show_batches=False):
	t = e.totals

	def line(label, amount, indent=0, bold=0, kind=""):
		return (label, flt(amount, 2), indent, bold, kind)

	def name_of(item):
		return item_names.get(item) or item

	def qty(v):
		v = flt(v)
		return frappe.format(v, {"fieldtype": "Float", "precision": 2 if v % 1 else 0})

	def item_lines(values, batches):
		out = []
		for item, value in sorted(values.items(), key=lambda x: name_of(x[0]).lower()):
			out.append(line(name_of(item), value, 1))
			if show_batches:
				out += [line(_("Batch {0} - Qty {1}").format(b, qty(q)), v, 2) for b, q, v in batches.get(item, [])]
		return out

	left = [line(_("Purchase (from Purchase Receipt)"), t.purchase_value, bold=1)]
	left += item_lines(e.purchase, e.purchase_batches)
	left.append(line(_("Shipment Expenses (shared per container)"), t.expenses, bold=1))
	left += [line(k, v, 1) for k, v in sorted(e.charges.items())]

	right = [line(_("Sales"), t.sales_value, bold=1)]
	right += item_lines(e.sales, e.sales_batches)
	right.append(line(_("Closing Stock (at landed cost)"), t.balance_value, bold=1))

	# balancing figure
	pct = _("{0}%").format(frappe.format(abs(flt(t.profit_pct, 2)), {"fieldtype": "Float", "precision": 2}))
	if t.profit >= 0:
		left.append(line(_("Net Profit ({0})").format(pct), t.profit, bold=1, kind="profit"))
	else:
		right.append(line(_("Net Loss ({0})").format(pct), -t.profit, bold=1, kind="loss"))
	side_total = max(t.total_cost, t.total_income)

	rows = [
		frappe._dict(
			row_type="title",
			expense=e.title,
			income=_("Qty: In {0} | Sold {1} | Wastage {2} | Stock {3}").format(
				qty(t.purchase_qty), qty(t.sold_qty), qty(t.other_out_qty), qty(t.balance_qty)
			),
		),
		frappe._dict(row_type="side_head", expense=_("Expenses"), income=_("Income")),
	]
	for i in range(max(len(left), len(right))):
		row = frappe._dict(row_type="line")
		if i < len(left):
			row.expense, row.expense_amount, row.l_indent, row.l_bold, row.l_kind = left[i]
		if i < len(right):
			row.income, row.income_amount, row.r_indent, row.r_bold, row.r_kind = right[i]
		rows.append(row)
	rows.append(
		frappe._dict(
			row_type="total",
			expense=_("Total"),
			expense_amount=flt(side_total, 2),
			income=_("Total"),
			income_amount=flt(side_total, 2),
		)
	)
	return rows


def get_currency(filters):
	company = filters.company or frappe.defaults.get_user_default("Company")
	return frappe.get_cached_value("Company", company, "default_currency") if company else None


def get_columns(currency):
	def money(fieldname):
		return {"label": _("Amount"), "fieldname": fieldname, "fieldtype": "Currency", "options": currency, "width": 150}

	return [
		{"label": _("Expenses"), "fieldname": "expense", "fieldtype": "Data", "width": 330},
		money("expense_amount"),
		{"label": _("Income"), "fieldname": "income", "fieldtype": "Data", "width": 330},
		money("income_amount"),
	]


def get_chart(entities):
	"""Expenses against Income per column (first 15)."""
	points = entities[:15]
	return {
		"data": {
			"labels": [e.label for e in points],
			"datasets": [
				{"name": _("Expenses"), "values": [flt(e.totals.total_cost, 2) for e in points]},
				{"name": _("Income"), "values": [flt(e.totals.total_income, 2) for e in points]},
			],
		},
		"type": "bar",
		"colors": ["#F59E0B", "#2563EB"],
		"fieldtype": "Currency",
	}


def get_report_summary(entities, currency):
	def total(field):
		return sum(flt(e.totals.get(field)) for e in entities)

	def money(label, value, indicator):
		return {"value": value, "label": label, "datatype": "Currency", "currency": currency, "indicator": indicator}

	profit = total("profit")
	return [
		money(_("Purchase"), total("purchase_value"), "Blue"),
		money(_("Shipment Expenses"), total("expenses"), "Orange"),
		money(_("Total Expenses"), total("total_cost"), "Red"),
		money(_("Sales"), total("sales_value"), "Blue"),
		money(_("Closing Stock"), total("balance_value"), "Cyan"),
		money(_("Profit / Loss"), profit, "Green" if profit >= 0 else "Red"),
	]
