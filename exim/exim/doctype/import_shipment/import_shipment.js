// Copyright (c) 2026, FinByz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Import Shipment", {
	setup(frm) {
		set_item_currency_options(frm);

		frm.set_query("charge_type", "charges", function() {
			return {
				filters: {
					is_stock_item: 0
				}
			};
		});

		frm.set_query("product", "items", function() {
			return {
				filters: {
					is_stock_item: 1
				}
			};
		});

		frm.set_query("cha", function() {
			return {
				filters: {
					supplier_group: "CHA"
				}
			};
		});

		frm.set_query("cfs_terminal", function() {
			return {
				filters: {
					supplier_group: "CFS"
				}
			};
		});

		frm.set_query("shipping_line", function() {
			return {
				filters: {
					supplier_group: "Shipping Line"
				}
			};
		});

		setup_container_details_queries(frm);
	},

	onload_post_render(frm) {
		setup_container_details_queries(frm);
	},

	items_add(frm) {
		setup_container_details_queries(frm);
	},

	items_remove(frm) {
		setup_container_details_queries(frm);
	},

	onload(frm) {
		if (frm.is_new()) {
			if (!frm.doc.company || frm.doc.company.includes("get_user_default")) {
				frm.set_value("company", frappe.defaults.get_user_default("Company") || frappe.defaults.get_default("company") || "");
			}
			if (!frm.doc.currency) {
				set_default_currency(frm);
			}
		}
	},

	refresh(frm) {
		render_link_documents(frm);
		setup_required_documents_grid(frm);
		add_print_attachments_button(frm);
		set_item_currency_options(frm);
		update_currency_labels(frm);
		frm.set_df_property("exchange_rate", "read_only", 1);
		frm.set_df_property("invoice_value", "read_only", 1);
		setup_container_details_queries(frm);

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				__("Purchase Order"),
				function () {
					erpnext.utils.map_current_doc({
						method: "exim.exim.doctype.import_shipment.import_shipment.make_import_shipment",
						source_doctype: "Purchase Order",
						target: frm,
						setters: {
							supplier: frm.doc.shipper || undefined,
						},
						get_query_filters: {
							docstatus: 1,
							status: ["not in", ["Closed", "On Hold", "Cancelled"]],
							per_received: ["<", 99.99],
						},
						allow_child_item_selection: true,
						child_fieldname: "items",
						child_columns: ["item_code", "item_name", "qty", "received_qty"],
					});
				},
				__("Get Items From")
			);
		}

		if (frm.doc.authorized_purchase_invoice || frm.doc.be_no) {
			frm.add_custom_button(
				__("Fetch BOE Taxes"),
				function () {
					fetch_boe_taxes(frm, true);
				},
				__("Actions")
			);
		}

		frm.add_custom_button(
			__("Sync Purchase Invoice"),
			function () {
				const pi = frm.doc.authorized_purchase_invoice || frm.doc.purchase_invoice;
				if (pi) {
					sync_commercial_details_from_pi(frm, pi, true);
				} else if (frm.doc.name && !frm.is_new()) {
					frappe.db.get_value("Purchase Invoice", {"import_shipment": frm.doc.name, "docstatus": ["!=", 2]}, ["name"]).then(r => {
						if (r && r.message && r.message.name) {
							sync_commercial_details_from_pi(frm, r.message.name, true);
						} else {
							frappe.msgprint(__("No Purchase Invoice linked to this Import Shipment."));
						}
					});
				} else {
					frappe.msgprint(__("Please save the Import Shipment or specify Purchase Invoice first."));
				}
			},
			__("Actions")
		);
	},

	purchase_invoice(frm) {
		if (frm.doc.purchase_invoice) {
			sync_commercial_details_from_pi(frm, frm.doc.purchase_invoice, true);
		}
	},

	authorized_purchase_invoice(frm) {
		if (frm.doc.authorized_purchase_invoice) {
			sync_commercial_details_from_pi(frm, frm.doc.authorized_purchase_invoice, true);
			fetch_boe_taxes(frm, true);
		}
	},

	duty_basic(frm) {
		frm.trigger("sync_custom_duty_charge");
	},

	sync_custom_duty_charge(frm) {
		const duty = flt(frm.doc.duty_basic);
		if (duty <= 0) return;

		let custom_duty_row = (frm.doc.charges || []).find(r => r.charge_type === "Custom Duty");
		if (custom_duty_row) {
			let needs_update = false;
			if (flt(custom_duty_row.amount) !== duty) {
				frappe.model.set_value(custom_duty_row.doctype, custom_duty_row.name, "amount", duty);
				needs_update = true;
			}
			if (flt(custom_duty_row.actual_amount) !== duty) {
				frappe.model.set_value(custom_duty_row.doctype, custom_duty_row.name, "actual_amount", duty);
				needs_update = true;
			}
			if (!custom_duty_row.item_name) {
				frappe.model.set_value(custom_duty_row.doctype, custom_duty_row.name, "item_name", "Custom Duty");
				needs_update = true;
			}
			if (needs_update) {
				frm.refresh_field("charges");
				frm.trigger("calculate_charge_totals");
			}
		} else {
			let empty_row = (frm.doc.charges || []).find(r => !r.charge_type && !flt(r.amount) && !flt(r.actual_amount));
			if (empty_row) {
				frappe.model.set_value(empty_row.doctype, empty_row.name, "charge_type", "Custom Duty");
				frappe.model.set_value(empty_row.doctype, empty_row.name, "item_name", "Custom Duty");
				frappe.model.set_value(empty_row.doctype, empty_row.name, "amount", duty);
				frappe.model.set_value(empty_row.doctype, empty_row.name, "actual_amount", duty);
			} else {
				let row = frm.add_child("charges");
				frappe.model.set_value(row.doctype, row.name, "charge_type", "Custom Duty");
				frappe.model.set_value(row.doctype, row.name, "item_name", "Custom Duty");
				frappe.model.set_value(row.doctype, row.name, "amount", duty);
				frappe.model.set_value(row.doctype, row.name, "actual_amount", duty);
			}
			frm.refresh_field("charges");
			frm.trigger("calculate_charge_totals");
		}
	},

	authorized_purchase_invoice(frm) {
		if (frm.doc.authorized_purchase_invoice) {
			fetch_boe_taxes(frm, true);
		}
	},

	be_no(frm) {
		if (frm.doc.be_no && !frm.doc.authorized_purchase_invoice) {
			fetch_boe_taxes(frm, false);
		}
	},

	destination_port(frm) {
		if (frm.doc.docstatus !== 0 || !frm.doc.destination_port) {
			return;
		}

		frappe.call({
			method: "exim.exim.doctype.import_shipment.import_shipment.get_charges_for_destination_port",
			args: {
				destination_port: frm.doc.destination_port
			},
			freeze: true,
			freeze_message: __("Fetching port charges..."),
			callback: function(r) {
				if (!r || !r.message || !r.message.length) {
					frappe.show_alert({
						message: __("No Import charges configured for port {0}", [frm.doc.destination_port]),
						indicator: "orange"
					});
					return;
				}

				const charges = r.message;

				const populate_charges = function() {
					frm.clear_table("charges");
					charges.forEach(function(item) {
						let row = frm.add_child("charges");
						row.charge_type = item.charge_type;
						row.item_name = item.item_name;
						row.amount = flt(item.amount);
					});
					frm.refresh_field("charges");
					frm.trigger("calculate_charge_totals");
					frappe.show_alert({
						message: __("Loaded {0} charge(s) for port {1}", [charges.length, frm.doc.destination_port]),
						indicator: "green"
					});
				};

				const has_existing = (frm.doc.charges || []).some(row => row.charge_type);
				if (has_existing) {
					frappe.confirm(
						__("Charges already exist in Import Shipment Charge table. Replace them with charges for destination port <b>{0}</b>?", [frm.doc.destination_port]),
						function() {
							populate_charges();
						}
					);
				} else {
					populate_charges();
				}
			}
		});
	},

	eta(frm) {
		if (frm.doc.eta) {
			const eta_date = frappe.datetime.str_to_obj(frm.doc.eta);
			if (eta_date) {
				const d = new Date(Date.UTC(eta_date.getFullYear(), eta_date.getMonth(), eta_date.getDate()));
				const dayNum = d.getUTCDay() || 7;
				d.setUTCDate(d.getUTCDate() + 4 - dayNum);
				const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
				const weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
				frm.set_value("week", weekNo);
			}
		} else {
			frm.set_value("week", null);
		}
	},

	company(frm) {
		if (frm.doc.company) {
			frappe.db.get_value("Company", frm.doc.company, "default_currency").then(r => {
				const comp_curr = (r && r.message && r.message.default_currency) || frappe.boot.sysdefaults.currency || "INR";
				if (!frm.doc.currency || frm.is_new()) {
					frm.set_value("currency", comp_curr);
				}
			});
		}
	},

	currency(frm) {
		const curr = frm.doc.currency || frappe.boot.sysdefaults.currency || "INR";
		(frm.doc.items || []).forEach(row => {
			frappe.model.set_value(row.doctype, row.name, "currency", curr);
		});
		update_currency_labels(frm);
		frm.refresh_field("items");
		frm.refresh_field("total_item_amount");
		frm.trigger("calculate_commercial_totals");
	},

	invoice_value(frm) {
		frm.trigger("calculate_commercial_totals");
	},

	exchange_rate(frm) {
		frm.trigger("calculate_item_totals");
		frm.trigger("calculate_commercial_totals");
		(frm.doc.items || []).forEach((row) => update_passing_rate_per_kg(frm, row.doctype, row.name));
	},

	insurance(frm) {
		frm.trigger("calculate_commercial_totals");
	},

	calculate_commercial_totals(frm) {
		const exchange_rate = flt(frm.doc.exchange_rate) || 1.0;
		const invoice_value = flt(frm.doc.invoice_value);
		const invoice_value_inr = invoice_value * exchange_rate;
		frm.set_value("invoice_value_inr", invoice_value_inr);
		frm.set_value("cif_value", invoice_value_inr + flt(frm.doc.insurance));
	},

	calculate_item_totals(frm) {
		const rate_multiplier = flt(frm.doc.exchange_rate) || 1.0;
		let total_boxes = 0;
		let total_net_weight = 0;
		let total_gross_weight = 0;
		let total_qty = 0;
		let total_item_amount = 0;
		let total_item_amount_inr = 0;

		(frm.doc.items || []).forEach(row => {
			const qty = flt(row.qty);
			const item_rate = flt(row.rate);
			const amount = qty * item_rate;
			const base_rate = item_rate * rate_multiplier;
			const base_amount = amount * rate_multiplier;

			frappe.model.set_value(row.doctype, row.name, {
				amount: amount,
				base_rate: base_rate,
				base_amount: base_amount
			});

			total_boxes += flt(row.boxes);
			total_net_weight += flt(row.net_weight);
			total_gross_weight += flt(row.gross_weight);
			total_qty += qty;
			total_item_amount += amount;
			total_item_amount_inr += base_amount;
		});

		frm.set_value("total_boxes", total_boxes);
		frm.set_value("total_net_weight", total_net_weight);
		frm.set_value("total_gross_weight", total_gross_weight);
		frm.set_value("total_qty", total_qty);
		frm.set_value("total_item_amount", total_item_amount);
		frm.set_value("total_item_amount_inr", total_item_amount_inr);
		frm.trigger("calculate_rates");
	},

	calculate_charge_totals(frm) {
		let total_expenses = 0;
		let total_actual_expenses = 0;

		(frm.doc.charges || []).forEach(row => {
			total_expenses += flt(row.amount);
			total_actual_expenses += flt(row.actual_amount);
		});

		frm.set_value("total_expenses", total_expenses);
		frm.set_value("total_actual_expenses", total_actual_expenses);
		frm.set_value("differ", total_actual_expenses - total_expenses);
		frm.trigger("calculate_rates");
	},

	calculate_rates(frm) {
		const total_base_item_amount = flt(frm.doc.total_item_amount_inr);
		const total_tentative_charges = flt(frm.doc.total_expenses);
		const total_actual_charges = flt(frm.doc.total_actual_expenses);

		(frm.doc.items || []).forEach(row => {
			const qty = flt(row.qty);
			const base_amount = flt(row.base_amount);

			if (total_base_item_amount > 0 && qty > 0) {
				const item_ratio = base_amount / total_base_item_amount;
				const allocated_tentative = total_tentative_charges * item_ratio;
				const allocated_actual = total_actual_charges * item_ratio;

				const tentative_rate = (base_amount + allocated_tentative) / qty;
				const landed_rate = (base_amount + allocated_actual) / qty;

				frappe.model.set_value(row.doctype, row.name, "tentative_rate", tentative_rate);
				frappe.model.set_value(row.doctype, row.name, "landed_rate", landed_rate);
			} else if (qty > 0) {
				frappe.model.set_value(row.doctype, row.name, "tentative_rate", flt(row.base_rate));
				frappe.model.set_value(row.doctype, row.name, "landed_rate", flt(row.base_rate));
			} else {
				frappe.model.set_value(row.doctype, row.name, "tentative_rate", 0);
				frappe.model.set_value(row.doctype, row.name, "landed_rate", 0);
			}
		});
		frm.refresh_field("items");
	}
});

const item_weight_cache = {};

function get_item_weight_per_unit(item_code, callback) {
	if (!item_code) {
		callback(0);
		return;
	}
	if (item_weight_cache[item_code] !== undefined) {
		callback(item_weight_cache[item_code]);
		return;
	}
	frappe.db.get_value("Item", item_code, "weight_per_unit").then(r => {
		const wpu = flt(r && r.message && r.message.weight_per_unit);
		item_weight_cache[item_code] = wpu;
		callback(wpu);
	});
}

const item_uom_factor_cache = {};

function get_item_uom_factors(item_code) {
	if (!item_code) return Promise.resolve({});
	if (item_uom_factor_cache[item_code]) return Promise.resolve(item_uom_factor_cache[item_code]);
	return frappe
		.xcall("exim.exim.doctype.import_shipment.import_shipment.get_item_uom_factors", { item_code })
		.then((data) => (item_uom_factor_cache[item_code] = data || {}));
}

function factor_for(factors, names) {
	const uom = Object.keys(factors || {}).find((u) => names.includes((u || "").trim().toLowerCase()));
	return uom ? flt(factors[uom]) : 0;
}

// Boxes = Qty / factor(UOM); Net Wt (kg) = Boxes x factor(Kg).
// Item UOM factor = how many of that UOM are in one Box (e.g. Kg = 9, Nos = 12).
// Same rule as set_boxes_and_net_weight() in import_shipment.py. Resolves false if Item has no Kg factor.
async function set_boxes_and_net_weight(frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.product || !flt(row.qty)) return false;

	const data = await get_item_uom_factors(row.product);
	const factors = data.factors || {};
	const kg_factor = factor_for(factors, ["kg", "kgs"]);
	const uom_factor = flt(factors[row.uom || data.stock_uom]);
	if (!kg_factor || !uom_factor) return false;

	const box_uoms = ["box", "boxes", "ctn", "carton"];
	const stock_units = flt(row.qty) / uom_factor;
	const box_factor = box_uoms.includes((data.stock_uom || "").toLowerCase())
		? flt(factors[data.stock_uom])
		: factor_for(factors, box_uoms);

	await frappe.model.set_value(cdt, cdn, {
		boxes: stock_units * (box_factor || 1),
		net_weight: stock_units * kg_factor,
	});
	return true;
}

// Passing Rate per KG = Passing Rate / (Net Wt / Qty); INR uses the shipment exchange rate.
function update_passing_rate_per_kg(frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !frappe.meta.has_field(cdt, "passing_rate_per_kg")) return;

	const kg_per_unit = flt(row.qty) ? flt(row.net_weight) / flt(row.qty) : 0;
	const passing_rate = flt(row.passing_rate);
	const values = {
		passing_rate_per_kg: kg_per_unit ? (passing_rate * flt(frm.doc.exchange_rate)) / kg_per_unit : 0,
	};
	if (frappe.meta.has_field(cdt, "passing_rate_per_kg_usd")) {
		values.passing_rate_per_kg_usd = kg_per_unit ? passing_rate / kg_per_unit : 0;
	}
	const changed = Object.keys(values).some((k) => flt(row[k]) !== flt(values[k]));
	if (changed) frappe.model.set_value(cdt, cdn, values);
}

async function update_item_net_weight(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row) return;

	const qty = flt(row.qty);

	if (await set_boxes_and_net_weight(frm, cdt, cdn)) {
		return; // net_weight handler recalculates totals and per-kg rates
	}

	if (row.product) {
		get_item_weight_per_unit(row.product, function(weight_per_unit) {
			if (weight_per_unit > 0) {
				frappe.model.set_value(cdt, cdn, "net_weight", qty * weight_per_unit);
			} else if (row.purchase_order_item) {
				frappe.db.get_value("Purchase Order Item", row.purchase_order_item, ["total_weight", "qty", "weight_per_unit"]).then(po_res => {
					const po_item = po_res && po_res.message;
					let unit_wt = flt(po_item && po_item.weight_per_unit);
					if (!unit_wt && flt(po_item && po_item.qty) > 0) {
						unit_wt = flt(po_item.total_weight) / flt(po_item.qty);
					}
					if (unit_wt > 0) {
						frappe.model.set_value(cdt, cdn, "net_weight", qty * unit_wt);
					} else {
						frm.trigger("calculate_item_totals");
					}
				});
			} else {
				frm.trigger("calculate_item_totals");
			}
		});
	} else {
		frm.trigger("calculate_item_totals");
	}
}

frappe.ui.form.on("Import Shipment Item", {
	items_add(frm, cdt, cdn) {
		const curr = frm.doc.currency || frappe.boot.sysdefaults.currency || "INR";
		frappe.model.set_value(cdt, cdn, "currency", curr);
	},

	product(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.product) {
			frappe.db.get_value("Item", row.product, ["item_name", "gst_hsn_code", "stock_uom", "weight_per_unit", "variety"]).then(r => {
				if (r && r.message) {
					const values_to_set = {
						item_name: r.message.item_name,
						hsn_code: r.message.gst_hsn_code,
						uom: r.message.stock_uom
					};
					if (!row.variety && r.message.variety) {
						values_to_set.variety = r.message.variety;
					}
					item_weight_cache[row.product] = flt(r.message.weight_per_unit);
					frappe.model.set_value(cdt, cdn, values_to_set).then(() => {
						if (flt(row.qty) > 0) update_item_net_weight(frm, cdt, cdn);
					});
				}
				setup_container_details_queries(frm);
			});
		} else {
			setup_container_details_queries(frm);
		}
	},

	qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const rate_multiplier = flt(frm.doc.exchange_rate) || 1.0;
		const amount = flt(row.qty) * flt(row.rate);
		frappe.model.set_value(cdt, cdn, {
			amount: amount,
			base_rate: flt(row.rate) * rate_multiplier,
			base_amount: amount * rate_multiplier
		});
		update_item_net_weight(frm, cdt, cdn);

		if (row.purchase_order_item && flt(row.qty) > 0) {
			frappe.call({
				method: "exim.exim.doctype.import_shipment.import_shipment.get_shipped_qty_for_po_item",
				args: {
					po_item_name: row.purchase_order_item,
					exclude_shipment: frm.is_new() ? null : frm.doc.name
				},
				callback: function(r) {
					const already_shipped = flt(r && r.message);
					frappe.db.get_value("Purchase Order Item", row.purchase_order_item, ["qty", "item_code", "parent"]).then(po_res => {
						const po_item = po_res && po_res.message;
						if (po_item) {
							const remaining = flt(po_item.qty) - already_shipped;
							if (flt(row.qty) > (remaining + 0.0001)) {
								frappe.msgprint({
									title: __("Quantity Exceeds Purchase Order"),
									message: __("Row #{0}: Quantity {1} for Item {2} exceeds the available quantity in Purchase Order {3}.<br><br>• Purchase Order Total: {4}<br>• Already Shipped: {5}<br>• Maximum Available: {6}", [
										row.idx,
										row.qty,
										frappe.bold(row.product || po_item.item_code),
										frappe.bold(row.purchase_order || po_item.parent),
										po_item.qty,
										already_shipped,
										Math.max(0, remaining)
									]),
									indicator: "orange"
								});
							}
						}
					});
				}
			});
		}
	},

	rate(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const rate_multiplier = flt(frm.doc.exchange_rate) || 1.0;
		const amount = flt(row.qty) * flt(row.rate);
		frappe.model.set_value(cdt, cdn, {
			amount: amount,
			base_rate: flt(row.rate) * rate_multiplier,
			base_amount: amount * rate_multiplier
		});
		frm.trigger("calculate_item_totals");
	},

	boxes(frm) {
		frm.trigger("calculate_item_totals");
	},

	net_weight(frm, cdt, cdn) {
		frm.trigger("calculate_item_totals");
		update_passing_rate_per_kg(frm, cdt, cdn);
	},

	uom(frm, cdt, cdn) {
		update_item_net_weight(frm, cdt, cdn);
	},

	passing_rate(frm, cdt, cdn) {
		update_passing_rate_per_kg(frm, cdt, cdn);
	},

	gross_weight(frm) {
		frm.trigger("calculate_item_totals");
	},

	items_remove(frm) {
		frm.trigger("calculate_item_totals");
	}
});

frappe.ui.form.on("Import Shipment Charge", {
	charge_type(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row && row.charge_type === "Custom Duty" && flt(frm.doc.duty_basic) > 0) {
			const duty = flt(frm.doc.duty_basic);
			frappe.model.set_value(cdt, cdn, "amount", duty);
			frappe.model.set_value(cdt, cdn, "actual_amount", duty);
			if (!row.item_name) {
				frappe.model.set_value(cdt, cdn, "item_name", "Custom Duty");
			}
		}
	},

	amount(frm) {
		frm.trigger("calculate_charge_totals");
	},

	actual_amount(frm) {
		frm.trigger("calculate_charge_totals");
	},

	charges_remove(frm) {
		frm.trigger("calculate_charge_totals");
	}
});

function fetch_boe_taxes(frm, show_alert = false) {
	if (!frm.doc.authorized_purchase_invoice && !frm.doc.be_no) {
		if (show_alert) {
			frappe.msgprint(__("Please specify Authorized Purchase Invoice or BE No. first."));
		}
		return;
	}

	frappe.call({
		method: "exim.exim.doctype.import_shipment.import_shipment.get_bill_of_entry_details",
		args: {
			shipment_name: frm.doc.name,
			authorized_purchase_invoice: frm.doc.authorized_purchase_invoice,
			be_no: frm.doc.be_no
		},
		callback: function (r) {
			if (r.message && r.message.has_boe) {
				const duty = flt(r.message.total_customs_duty);
				const taxes = flt(r.message.total_taxes);

				let updated = false;
				if (flt(frm.doc.duty_basic) !== duty) {
					frm.set_value("duty_basic", duty);
					updated = true;
				}
				if (flt(frm.doc.cess_and_gst) !== taxes) {
					frm.set_value("cess_and_gst", taxes);
					updated = true;
				}
				if (!frm.doc.be_no && r.message.bill_of_entry_no) {
					frm.set_value("be_no", r.message.bill_of_entry_no);
					updated = true;
				}
				if (!frm.doc.be_date && r.message.bill_of_entry_date) {
					frm.set_value("be_date", r.message.bill_of_entry_date);
					updated = true;
				}

				if (duty > 0) {
					frm.trigger("sync_custom_duty_charge");
				}

				if (show_alert) {
					frappe.show_alert({
						message: __("Updated Duty Basic ({0}) and CESS + GST ({1}) from Bill of Entry.", [
							format_currency(duty),
							format_currency(taxes)
						]),
						indicator: "green"
					});
				}
			} else if (show_alert) {
				frappe.msgprint(__("No related Bill of Entry found for Authorized Purchase Invoice {0}.", [
					frm.doc.authorized_purchase_invoice || ""
				]));
			}
		}
	});
}

function set_item_currency_options(frm) {
	let grid = frm.fields_dict["items"] && frm.fields_dict["items"].grid;
	if (grid && grid.docfields) {
		["rate", "amount", "passing_rate"].forEach(fieldname => {
			let df = frappe.utils.filter_dict(grid.docfields, { fieldname: fieldname })[0];
			if (df) {
				df.options = "currency";
			}
		});
		["base_rate", "base_amount", "tentative_rate", "landed_rate"].forEach(fieldname => {
			let df = frappe.utils.filter_dict(grid.docfields, { fieldname: fieldname })[0];
			if (df) {
				df.options = "";
			}
		});
	}
	let df_total = frappe.meta.get_docfield("Import Shipment", "total_item_amount", frm.doc.name);
	if (df_total) {
		df_total.options = "currency";
	}
	let df_total_inr = frappe.meta.get_docfield("Import Shipment", "total_item_amount_inr", frm.doc.name);
	if (df_total_inr) {
		df_total_inr.options = "";
	}
}

function update_currency_labels(frm) {
	set_item_currency_options(frm);
	const curr = frm.doc.currency || frappe.boot.sysdefaults.currency || "INR";
	if (frm.set_currency_labels) {
		frm.set_currency_labels(["total_item_amount", "invoice_value"], curr);
		frm.set_currency_labels(["rate", "amount"], curr, "items");
	}
}

function set_default_currency(frm) {
	if (frm.doc.company) {
		frappe.db.get_value("Company", frm.doc.company, "default_currency").then(r => {
			const comp_curr = (r && r.message && r.message.default_currency) || frappe.boot.sysdefaults.currency || "INR";
			if (!frm.doc.currency) {
				frm.set_value("currency", comp_curr);
			}
		});
	} else {
		const def_curr = frappe.boot.sysdefaults.currency || "INR";
		if (!frm.doc.currency) {
			frm.set_value("currency", def_curr);
		}
	}
}

function sync_commercial_details_from_pi(frm, pi_name, show_alert = false) {
	if (!pi_name) return;
	frappe.db.get_value("Purchase Invoice", pi_name, [
		"name", "grand_total", "base_grand_total", "conversion_rate",
		"bill_no", "bill_date", "currency", "posting_date", "authority", "unauthorized_purchase_invoice"
	]).then(r => {
		if (r && r.message) {
			const pi = r.message;
			const inv_val = flt(pi.grand_total);
			const conv_rate = flt(pi.conversion_rate) > 0 ? flt(pi.conversion_rate) : (flt(frm.doc.exchange_rate) || 1.0);
			const inv_val_inr = flt(pi.base_grand_total) > 0 ? flt(pi.base_grand_total) : (inv_val * conv_rate);

			let updated = false;
			if (flt(frm.doc.invoice_value) !== inv_val) {
				frm.set_value("invoice_value", inv_val);
				updated = true;
			}
			if (flt(frm.doc.exchange_rate) !== conv_rate) {
				frm.set_value("exchange_rate", conv_rate);
				updated = true;
			}
			if (flt(frm.doc.invoice_value_inr) !== inv_val_inr) {
				frm.set_value("invoice_value_inr", inv_val_inr);
				updated = true;
			}
			const new_cif = inv_val_inr + flt(frm.doc.insurance);
			if (flt(frm.doc.cif_value) !== new_cif) {
				frm.set_value("cif_value", new_cif);
				updated = true;
			}

			if (pi.bill_no && frm.doc.invoice_no !== pi.bill_no) {
				frm.set_value("invoice_no", pi.bill_no);
				updated = true;
			}
			if (pi.bill_date && frm.doc.invoice_date !== pi.bill_date) {
				frm.set_value("invoice_date", pi.bill_date);
				updated = true;
			}
			if (pi.currency && frm.doc.currency !== pi.currency) {
				frm.set_value("currency", pi.currency);
				updated = true;
			}

			const is_auth = (pi.authority && String(pi.authority).trim().toLowerCase() === "authorized") || !!pi.unauthorized_purchase_invoice;
			if (is_auth && frm.doc.authorized_purchase_invoice !== pi.name) {
				frm.set_value("authorized_purchase_invoice", pi.name);
				updated = true;
			} else if (!is_auth && frm.doc.purchase_invoice !== pi.name) {
				frm.set_value("purchase_invoice", pi.name);
				updated = true;
			}

			if (show_alert && updated) {
				frappe.show_alert({
					message: __("Updated Commercial details from Purchase Invoice {0} (Value: {1})", [
						pi.name,
						format_currency(inv_val, pi.currency || frm.doc.currency)
					]),
					indicator: "green"
				});
			}
		}
	});
}

frappe.ui.form.on("Import Shipment Container Details", {
	form_render(frm, cdt, cdn) {
		setup_container_details_queries(frm);
	},
	container_details_add(frm, cdt, cdn) {
		setup_container_details_queries(frm);
		sync_container_summary_from_details(frm);
	},
	container_details_remove(frm) {
		sync_container_summary_from_details(frm);
	},
	item_code(frm, cdt, cdn) {
		let row = locals[cdt] && locals[cdt][cdn];
		if (!row || !row.item_code) return;

		let valid_items = (frm.doc.items || [])
			.map((d) => d.product || d.item_code)
			.filter(Boolean);
		if (valid_items.length && !valid_items.includes(row.item_code)) {
			frappe.msgprint(
				__("Item {0} is not present in the Shipment Items table.", [frappe.bold(row.item_code)])
			);
			frappe.model.set_value(cdt, cdn, "item_code", "");
			frappe.model.set_value(cdt, cdn, "item_name", "");
			return;
		}

		frappe.db.get_value("Item", row.item_code, "item_name", (r) => {
			if (r && r.item_name) {
				frappe.model.set_value(cdt, cdn, "item_name", r.item_name);
			}
		});
	},
	container(frm, cdt, cdn) {
		sync_container_summary_from_details(frm);
	}
});

function setup_container_details_queries(frm) {
	if (!frm.fields_dict.container_details || !frm.fields_dict.container_details.grid) return;

	let container_query = function() {
		return {
			filters: {
				"enable": 1
			}
		};
	};

	let item_query = function(doc, cdt, cdn) {
		let parent_doc = doc || frm.doc;
		let items = (parent_doc.items || [])
			.map((d) => d.product || d.item_code)
			.filter(Boolean);
		items = [...new Set(items)];

		if (!items.length) {
			return {
				filters: {
					name: ["in", ["__NONE__"]]
				}
			};
		}

		return {
			filters: {
				name: ["in", items]
			}
		};
	};

	frm.set_query("container", "container_details", container_query);
	frm.set_query("item_code", "container_details", item_query);

	let grid = frm.fields_dict.container_details.grid;
	if (grid) {
		grid.get_field("container").get_query = container_query;
		grid.get_field("item_code").get_query = item_query;

		(grid.grid_rows || []).forEach((row) => {
			(row.columns_list || []).forEach((col) => {
				if (col.df && col.df.fieldname === "item_code" && col.field) {
					col.field.get_query = item_query;
				}
				if (col.df && col.df.fieldname === "container" && col.field) {
					col.field.get_query = container_query;
				}
			});
			if (row.grid_form && row.grid_form.fields_dict) {
				if (row.grid_form.fields_dict.item_code) {
					row.grid_form.fields_dict.item_code.get_query = item_query;
				}
				if (row.grid_form.fields_dict.container) {
					row.grid_form.fields_dict.container.get_query = container_query;
				}
			}
		});
	}
}

function sync_container_summary_from_details(frm) {
	let rows = frm.doc.container_details || [];
	let distinct_containers = [...new Set(rows.map((r) => r.container).filter(Boolean))];
	if (distinct_containers.length > 0) {
		frm.set_value("no_of_containers", distinct_containers.length);
		frm.set_value("container_nos", distinct_containers.join(", "));
	} else {
		frm.set_value("no_of_containers", 0);
		frm.set_value("container_nos", "");
	}
}

// Required Documents (shared child table): on Import Shipment the attachment is the
// "Draft Document" and a "Final Document" column is shown next to it. Other forms keep "Attachment".
function setup_required_documents_grid(frm) {
	const field = frm.fields_dict.required_documents;
	const grid = field && field.grid;
	if (!grid || grid.__exim_draft_final) return;
	grid.__exim_draft_final = true;

	const set_prop = (fieldname, prop, value) => {
		// grid.docfields is this form's copy, so other forms keep their labels
		(grid.docfields || []).forEach((df) => df.fieldname === fieldname && (df[prop] = value));
		(grid.grid_rows || []).forEach((row) =>
			(row.docfields || []).forEach((df) => df.fieldname === fieldname && (df[prop] = value))
		);
	};

	set_prop("attachment", "label", __("Draft Document"));
	if (frappe.meta.has_field("Required Document", "final_document")) {
		set_prop("final_document", "in_list_view", 1);
		set_prop("final_document", "columns", 2);
	}
	// rebuild the grid header/columns with the new labels
	grid.visible_columns = [];
	grid.refresh();
}


frappe.ui.form.on("Required Document", {
	// expanded row form: rows added after load carry their own field copy
	form_render(frm, cdt, cdn) {
		if (frm.doctype !== "Import Shipment") return;
		const grid_row = frm.fields_dict.required_documents.grid.get_row(cdn);
		const field = grid_row && grid_row.grid_form && grid_row.grid_form.fields_dict.attachment;
		if (field && field.df.label !== __("Draft Document")) {
			field.df.label = __("Draft Document");
			field.refresh();
		}
	},
});

// One PDF with only the attached files (Draft + Final of each Required Document):
// PDF pages as they are, each image as a page. Word/other files cannot be converted.
function add_print_attachments_button(frm) {
	if (frm.is_new()) return;
	const urls = [];
	(frm.doc.required_documents || []).forEach((row) => {
		[row.attachment, row.final_document].forEach((u) => u && !urls.includes(u) && urls.push(u));
	});
	if (!urls.length) return;

	frm.add_custom_button(__("Print Attachments"), () => {
		const printable = ["pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff"];
		const ext = (u) => (u.split("?")[0].split(".").pop() || "").toLowerCase();
		const skipped = urls.filter((u) => !printable.includes(ext(u)));
		if (skipped.length === urls.length) {
			frappe.msgprint(__("Only PDF and image attachments can be printed."));
			return;
		}
		if (skipped.length) {
			frappe.show_alert({
				message: __("Not included (only PDF and images can be printed): {0}", [
					skipped.map((u) => u.split("/").pop()).join(", "),
				]),
				indicator: "orange",
			}, 10);
		}
		const url = `/api/method/exim.exim.utils.shipment_attachments.download_attachments_pdf?name=${encodeURIComponent(frm.doc.name)}`;
		const w = window.open(frappe.urllib.get_full_url(url));
		if (!w) frappe.msgprint(__("Please enable pop-ups"));
	});
}

const LINK_DOCUMENT_COLOURS = {
	"Purchase Order": ["#6D5BD0", "#EEEBFB"],
	"Purchase Receipt": ["#EA7A1E", "#FDEEE0"],
	"Unloading Checklist": ["#7C3AED", "#F1E9FD"],
	"Purchase Invoice": ["#0891B2", "#E0F4F8"],
	"Bill of Entry": ["#DC2626", "#FDE8E8"],
	"Payment Entry": ["#16A34A", "#E3F5E9"],
};

function render_link_documents(frm) {
	const field = frm.fields_dict.link_documents_html;
	if (!field) return;
	const wrapper = field.$wrapper;
	if (frm.is_new()) {
		wrapper.html(`<p class="text-muted">${__("Save the shipment to see its linked documents.")}</p>`);
		return;
	}

	frappe.call({
		method: "exim.exim.doctype.import_shipment.import_shipment.get_link_documents",
		args: { shipment: frm.doc.name },
		callback(r) {
			const esc = frappe.utils.escape_html;
			const rows = (r.message || []).map((g) => {
				const [fg, bg] = LINK_DOCUMENT_COLOURS[g.doctype] || ["#475569", "#F1F5F9"];
				const chips = g.names
					.map(
						(n) => `<a class="ld-chip" href="${frappe.utils.get_form_link(g.doctype, n)}">${esc(n)}</a>`
					)
					.join("");
				const count = g.names.length > 1 ? `<a class="ld-count" data-list="${esc(g.doctype)}" title="${__("View all")}">${g.names.length}</a>` : "";
				const add = g.can_create
					? `<button class="btn btn-xs btn-default ld-add" data-new="${esc(g.doctype)}" title="${__("Create new {0}", [__(g.doctype)])}">+</button>`
					: "";
				return `<div class="ld-row">
					<span class="ld-icon" style="color:${fg};background:${bg}">${esc(g.doctype.charAt(0))}</span>
					<a class="ld-label" data-list="${esc(g.doctype)}">${__(g.doctype)}</a>${count}
					<span class="ld-chips">${chips}</span>${add}
				</div>`;
			});

			wrapper.html(`<style>
				.ld-card{border:1px solid var(--border-color);border-radius:12px;padding:4px 20px;max-width:900px}
				.ld-row{display:flex;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid var(--border-color)}
				.ld-row:last-child{border-bottom:0}
				.ld-icon{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:600;flex:none}
				.ld-label{width:170px;font-weight:600;color:var(--text-color);cursor:pointer;flex:none}
				.ld-count{background:var(--control-bg);border-radius:10px;padding:0 7px;font-size:11px;color:var(--text-muted);margin-left:-6px;cursor:pointer}
				.ld-chips{display:flex;flex-wrap:wrap;gap:8px;flex:1}
				.ld-chip{background:#EAF1FE;border:1px solid #C9DAFB;color:#2563EB;border-radius:8px;padding:5px 12px;font-weight:600;font-size:12px}
				.ld-add{margin-left:auto;flex:none}
			</style><div class="ld-card">${rows.join("")}</div>`);

			wrapper.find("[data-list]").on("click", function () {
				const doctype = $(this).data("list");
				const group = (r.message || []).find((g) => g.doctype === doctype);
				if (!group || !group.names.length) {
					frappe.set_route("List", doctype);
				} else if (group.has_link_field) {
					frappe.set_route("List", doctype, { import_shipment: frm.doc.name });
				} else {
					frappe.set_route("List", doctype, { name: ["in", group.names] });
				}
			});

			wrapper.find("[data-new]").on("click", function () {
				const doctype = $(this).data("new");
				const group = (r.message || []).find((g) => g.doctype === doctype) || {};
				frappe.new_doc(doctype, group.has_link_field ? { import_shipment: frm.doc.name } : {});
			});
		},
	});
}
