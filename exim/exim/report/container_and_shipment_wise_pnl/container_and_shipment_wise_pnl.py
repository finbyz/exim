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
from frappe.utils import cint, flt, getdate

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

	# a picked shipment or container is shown whatever its date; the range only narrows "all shipments"
	use_dates = not (filters.import_shipment or filters.container)
	from_date = getdate(filters.from_date) if use_dates and filters.from_date else None
	to_date = getdate(filters.to_date) if use_dates and filters.to_date else None
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
# T format, like a Trading / P&L account: cost on the left, realisation on the right, one block per container
# (Container Wise) or per shipment (Shipment Wise), plus a combined block when there are several.
# Each block is a tree. Its groups pair one heading from each side (Purchase | Sales, Shipment Expenses |
# Closing Stock, Key Figures): collapsed they show the totals, expanded they list every item and every charge.
# Net Profit sits on the cost side and Net Loss on the realisation side, so both sides add up to the same total.

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
ITEM_FIELDS = ("p_qty", "p_val", "s_qty", "s_val", "b_qty", "b_val", "o_qty")


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


def new_item():
	return frappe._dict({f: 0.0 for f in ITEM_FIELDS}, batches=[])


def make_entity(label, title, containers, charges=None):
	"""Per item: purchased, sold, in stock and wasted qty / value, plus the shipment charges by name."""
	e = frappe._dict(label=label, title=title, item_stats=defaultdict(new_item))
	e.charges = defaultdict(float, charges or {})
	for c in containers:
		if charges is None:
			for name, amount in c.charges.items():
				e.charges[name] += amount
		for batch_no, b in sorted(c.batches.items()):
			it = e.item_stats[b.item_code or _("Unknown Item")]
			values = dict(
				p_qty=flt(b.purchase_qty),
				p_val=flt(b.purchase_value),
				s_qty=flt(b.sold_qty),
				s_val=flt(b.sales_value),
				b_qty=max(flt(b.balance_qty), 0),
				b_val=flt(b.balance_value),
				o_qty=flt(b.other_out_qty),
			)
			for f, v in values.items():
				it[f] += v
			batch = _("{0} (from {1})").format(batch_no, b.source_batch) if b.source_batch else batch_no
			it.batches.append(frappe._dict(values, batch=batch))

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
	t.status = status_of(t)


def combine(entities, title):
	e = frappe._dict(label=_("Total"), title=title, item_stats=defaultdict(new_item), charges=defaultdict(float))
	for x in entities:
		for k, v in x.charges.items():
			e.charges[k] += v
		for item, it in x.item_stats.items():
			for f in ITEM_FIELDS:
				e.item_stats[item][f] += it[f]
	e.totals = frappe._dict({f: sum(flt(x.totals.get(f)) for x in entities) for f in TOTAL_FIELDS})
	set_totals(e.totals)
	return e


def get_data(entities, filters):
	codes = list({i for e in entities for i in e.item_stats})
	item_names = (
		dict(frappe.get_all("Item", filters={"name": ("in", codes)}, fields=["name", "item_name"], as_list=True))
		if codes
		else {}
	)

	blocks = list(entities)
	if len(entities) > 1:
		what = _("Shipments") if filters.get("view") == "Shipment Wise" else _("Containers")
		blocks.append(combine(entities, _("Total of {0} {1}").format(len(entities), what)))

	data = []
	for i, e in enumerate(blocks):
		if i:
			data.append(frappe._dict(row_id=f"gap{i}", indent=0, row_type="gap"))
		data += t_block(e, f"b{i}", item_names, filters.get("show_batches") and e.label != _("Total"))
	return data


def rate(value, qty):
	return flt(value) / flt(qty) if flt(qty) else None


def pct(part, whole):
	value = flt(part) / flt(whole) * 100 if flt(whole) else 0.0
	return frappe.format(flt(value, 2), {"fieldtype": "Float", "precision": 2}) + "%"


def side(label, qty=None, rate_=None, amount=None, bold=0, sub=0, kind=""):
	"""One side of a T row."""
	return frappe._dict(label=label, qty=qty, rate=rate_, amount=amount, bold=bold, sub=sub, kind=kind)


def t_block(e, block_id, item_names, show_batches=False):
	t = e.totals

	def name_of(item):
		return item_names.get(item) or item

	def item_sides(qty_f, val_f, rate_of=rate):
		out = []
		for item, it in sorted(e.item_stats.items(), key=lambda x: name_of(x[0]).lower()):
			if not flt(it[qty_f]) and not flt(it[val_f]):
				continue
			out.append(side(name_of(item), it[qty_f], rate_of(it[val_f], it[qty_f]), it[val_f]))
			if show_batches:
				for b in it.get("batches") or []:
					if flt(b[qty_f]) or flt(b[val_f]):
						out.append(side(_("Batch {0}").format(b.batch), b[qty_f], rate_of(b[val_f], b[qty_f]), b[val_f], sub=1))
		return out

	rows = []

	def add(row_id, parent, indent, row_type, left=None, right=None):
		row = frappe._dict(row_id=f"{block_id}:{row_id}", parent_row=f"{block_id}:{parent}" if parent else None, indent=indent, row_type=row_type)
		for prefix, s in (("e", left), ("i", right)):
			if not s:
				continue
			row["expense" if prefix == "e" else "income"] = s.label
			row[f"{prefix}_qty"], row[f"{prefix}_rate"], row[f"{prefix}_amount"] = s.qty, s.rate, s.amount
			row[f"{prefix}_bold"], row[f"{prefix}_sub"], row[f"{prefix}_kind"] = s.bold, s.sub, s.kind
		rows.append(row)

	def add_pairs(parent, lefts, rights):
		for n in range(max(len(lefts), len(rights))):
			add(f"{parent}:{n}", parent, 2, "detail", lefts[n] if n < len(lefts) else None, rights[n] if n < len(rights) else None)

	add("title", None, 0, "title", side(e.title), side(_("Status: {0}").format(t.status)))
	add("head", "title", 1, "side_head", side(_("Cost")), side(_("Realisation")))

	# Purchase | Sales
	add(
		"trade",
		"title",
		1,
		"group",
		side(_("Purchase (Purchase Receipt)"), t.purchase_qty, rate(t.purchase_value, t.purchase_qty), t.purchase_value, bold=1),
		side(_("Sales"), t.sold_qty, rate(t.sales_value, t.sold_qty), t.sales_value, bold=1),
	)
	add_pairs("trade", item_sides("p_qty", "p_val"), item_sides("s_qty", "s_val"))

	# Shipment Expenses | Closing Stock
	stock = item_sides("b_qty", "b_val")
	if flt(t.other_out_qty):
		stock.append(side(_("Wastage / Other Out (qty, no value)"), t.other_out_qty))
	add(
		"exp",
		"title",
		1,
		"group",
		side(_("Shipment Expenses"), amount=t.expenses, bold=1),
		side(_("Closing Stock (at landed cost)"), t.balance_qty, rate(t.balance_value, t.balance_qty), t.balance_value, bold=1),
	)
	add_pairs("exp", [side(k, amount=v) for k, v in sorted(e.charges.items())], stock)

	# balancing figure, then the equal totals
	side_total = max(t.total_cost, t.total_income)
	if t.profit >= 0:
		add("net", "title", 1, "net", left=side(_("Net Profit"), amount=t.profit, bold=1, kind="profit"))
	else:
		add("net", "title", 1, "net", right=side(_("Net Loss"), amount=-t.profit, bold=1, kind="loss"))
	add("total", "title", 1, "total", side(_("Total"), amount=side_total, bold=1), side(_("Total"), amount=side_total, bold=1))

	# Key figures
	add("keys", "title", 1, "group", side(_("Key Figures"), bold=1), side(""))
	add_pairs(
		"keys",
		[
			side(_("Landed Cost per Unit"), rate_=rate(t.total_cost, t.purchase_qty)),
			side(_("Expenses on Purchase: {0}").format(pct(t.expenses, t.purchase_value))),
			side(_("Profit / Loss on Cost: {0}").format(pct(t.profit, t.total_cost)), kind="profit" if t.profit >= 0 else "loss"),
		],
		[
			side(_("Average Sale Rate per Unit"), rate_=rate(t.sales_value, t.sold_qty)),
			side(_("Qty Sold: {0} of purchased").format(pct(t.sold_qty, t.purchase_qty))),
			side(_("Qty in Stock: {0} of purchased").format(pct(t.balance_qty, t.purchase_qty))),
		],
	)
	return rows


def get_currency(filters):
	company = filters.company or frappe.defaults.get_user_default("Company")
	return frappe.get_cached_value("Company", company, "default_currency") if company else None


def get_columns(currency):
	def money(label, fieldname, width=120):
		return {"label": label, "fieldname": fieldname, "fieldtype": "Currency", "options": currency, "width": width}

	def qty(fieldname):
		return {"label": _("Qty"), "fieldname": fieldname, "fieldtype": "Float", "width": 85}

	return [
		{"label": _("Cost"), "fieldname": "expense", "fieldtype": "Data", "width": 260},
		qty("e_qty"),
		money(_("Rate"), "e_rate", 100),
		money(_("Amount"), "e_amount"),
		{"label": _("Realisation"), "fieldname": "income", "fieldtype": "Data", "width": 260},
		qty("i_qty"),
		money(_("Rate"), "i_rate", 100),
		money(_("Amount"), "i_amount"),
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


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def container_query(doctype, txt, searchfield, start, page_len, filters):
	"""Container filter: containers of the selected Import Shipment (else of every shipment the user can read)."""
	filters = frappe._dict(filters or {})
	conditions = {"status": ("!=", "Cancelled")}
	if filters.company:
		conditions["company"] = filters.company
	if filters.import_shipment:
		conditions["name"] = filters.import_shipment
	shipments = frappe.get_list("Import Shipment", filters=conditions, pluck="name")
	if not shipments:
		return []

	rows = frappe.get_all(
		"Import Shipment Container Details",
		filters={
			"parent": ("in", shipments),
			"parenttype": "Import Shipment",
			"container": ("like", f"%{txt}%"),
		},
		fields=["container", "parent"],
		order_by="parent desc, idx asc",
	)
	seen, out = set(), []
	for r in rows:
		if r.container and r.container not in seen:
			seen.add(r.container)
			out.append([r.container, r.parent])
	return out[cint(start) : cint(start) + cint(page_len)]
