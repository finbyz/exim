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
		set_item_currency_options(frm);
		update_currency_labels(frm);
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

			// Auto-sync on refresh if duty_basic or cess_and_gst are not populated yet
			if (!flt(frm.doc.duty_basic) && !flt(frm.doc.cess_and_gst)) {
				fetch_boe_taxes(frm, false);
			}
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

function update_item_net_weight(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row) return;

	const qty = flt(row.qty);

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
					frappe.model.set_value(cdt, cdn, values_to_set);
					const wpu = flt(r.message.weight_per_unit);
					item_weight_cache[row.product] = wpu;
					if (wpu > 0 && flt(row.qty) > 0) {
						frappe.model.set_value(cdt, cdn, "net_weight", flt(row.qty) * wpu);
					}
				}
			});
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

	net_weight(frm) {
		frm.trigger("calculate_item_totals");
	},

	gross_weight(frm) {
		frm.trigger("calculate_item_totals");
	},

	items_remove(frm) {
		frm.trigger("calculate_item_totals");
	}
});

frappe.ui.form.on("Import Shipment Charge", {
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
