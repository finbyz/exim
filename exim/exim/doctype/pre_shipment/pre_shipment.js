 // Copyright (c) 2018, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

let set_currency = 0;

frappe.ui.form.on("Pre Shipment", {

	setup(frm) {

		// add_fetch
		frm.add_fetch('forward_contract', 'booking_rate', 'forward_rate');
		frm.add_fetch('forward_contract', 'amount', 'forward_amount');
		frm.add_fetch('forward_contract', 'maturity_from', 'maturity_from');
		frm.add_fetch('forward_contract', 'maturity_to', 'maturity_to');
		frm.add_fetch('forward_contract', 'amount_outstanding', 'amount_outstanding');
		frm.add_fetch('forward_contract', 'amount_outstanding', 'amount_utilized');

		// funding_bank
		frm.set_query("funding_bank", function () {
			return {
				filters: {
					bank_type: "Indian Bank"
				}
			};
		});

		// supplier_bank
		frm.set_query("supplier_bank", function () {
			return {
				filters: {
					bank_type: "Foreign Bank"
				}
			};
		});

		// loan_account
		frm.set_query("loan_account", function () {
			return {
				filters: {
					account_type: "Bank",
					account_currency: frm.doc.credit_currency
				}
			};
		});

		// loan_credit_account
		frm.set_query("loan_credit_account", function () {
			return {
				filters: {
					account_type: "Bank"
				}
			};
		});

		// forward_contract child table query
		frm.set_query("forward_contract", "forwards", function () {
			return {
				filters: {
					hedge: "Export",
					status: "Open",
					docstatus: 1,
					amount_outstanding: ['>', '0'],
					currency: frm.doc.credit_currency
				}
			};
		});
	},

	refresh(frm) {

		if (frm.doc.docstatus === 1 && !frm.doc.running) {

			frm.set_df_property("document", "read_only", 1);
			frm.set_df_property("against", "read_only", 1);
			frm.set_df_property("running", "read_only", 1);
		}
	},

	onload(frm) {

		if (frm.doc.__islocal) {
			frm.set_value("credit_currency", "USD");
		}

		frm.events.set_currency_lables(frm);
		frm.events.set_due_date(frm);
	},

	against(frm) {

		frm.set_value('document', '');
		frm.set_value('underline_currency', '');
		frm.set_value('total_amount', 0.0);
		frm.set_value('total_amount_inr', 0.0);
	},

	document(frm) {

		if (frm.doc.document) {

			frappe.call({
				method: 'get_document_details',
				doc: frm.doc,

				callback: function (r) {

					if (!r.exc) {

						$.each(r.message, function (k, v) {
							frm.set_value(k, v);
						});
					}
				}
			});

		} else {

			frm.set_value('total_amount', 0.0);
			frm.set_value('total_amount_inr', 0.0);
		}
	},

	posting_date(frm) {
		frm.events.set_due_date(frm);
	},

	loan_tenure(frm) {
		frm.events.set_due_date(frm);
	},

	source_exchange_rate(frm) {

		if (frm.doc.source_exchange_rate && frm.doc.loan_amount) {

			let loan_amount_inr =
				flt(frm.doc.source_exchange_rate * frm.doc.loan_amount);

			frm.set_value('loan_amount_inr', loan_amount_inr);
		}
	},

	loan_amount(frm) {

		frm.set_value(
			'loan_outstanding_amount',
			frm.doc.loan_amount
		);

		if (frm.doc.source_exchange_rate && frm.doc.loan_amount) {

			const loan_amount_inr =
				flt(frm.doc.source_exchange_rate * frm.doc.loan_amount);

			frm.set_value('loan_amount_inr', loan_amount_inr);
		}

		frm.trigger('cal_cash_amount');
	},

	loan_amount_inr(frm) {

		frm.set_value(
			'loan_outstanding_amount_inr',
			frm.doc.loan_amount_inr
		);
	},

	total_amount_utilized(frm) {
		frm.trigger('cal_cash_amount');
	},

	cal_cash_amount(frm) {

		const cash_amount =
			flt(frm.doc.loan_amount) -
			flt(frm.doc.total_amount_utilized);

		frm.set_value('cash_amount', cash_amount);
	},

	credit_currency(frm) {

		if (frm.doc.credit_currency === 'INR' && !set_currency) {

			frm.set_value("credit_currency", "USD");
			set_currency = 1;
		}

		frm.events.clear_forward_details(frm);

		if (frm.doc.credit_currency) {

			frm.events.get_exchange_rate(frm);
			frm.events.set_currency_lables(frm);

		} else {

			frm.set_df_property(
				"source_exchange_rate",
				"description",
				""
			);
		}
	},

	set_currency_lables(frm) {

		frm.set_df_property(
			"loan_amount_inr",
			"read_only",
			frm.doc.credit_currency === 'INR' ? 0 : 1
		);

		frm.set_df_property(
			"amount_utilized",
			"options",
			"credit_currency",
			frm.doc.name,
			"forwards"
		);

		frm.set_df_property(
			"forward_amount",
			"options",
			"credit_currency",
			frm.doc.name,
			"forwards"
		);

		frm.set_df_property(
			"amount_outstanding",
			"options",
			"credit_currency",
			frm.doc.name,
			"forwards"
		);

		let company_currency = frm.doc.company
			? frappe.get_doc(":Company", frm.doc.company).default_currency
			: "";

		frm.set_df_property(
			"source_exchange_rate",
			"description",
			`1 ${frm.doc.credit_currency} = [?] ${company_currency}`
		);

		frm.set_currency_labels(
			["loan_amount"],
			frm.doc.credit_currency
		);
	},

	get_exchange_rate(frm) {

		let company_currency =
			frappe.get_doc(":Company", frm.doc.company).default_currency;

		frappe.call({
			method: "erpnext.setup.utils.get_exchange_rate",

			args: {
				from_currency: frm.doc.credit_currency,
				to_currency: company_currency,
				transaction_date: frm.doc.posting_date
			},

			callback: function (r) {
				frm.set_value("source_exchange_rate", r.message);
			}
		});
	},

	clear_forward_details(frm) {

		frm.clear_table('forwards');

		frm.events.cal_average_forward_rate(frm);
		frm.events.cal_total_amount_utilized(frm);

		frm.refresh_field('forwards');
	},

	set_due_date(frm) {

		let due_date = frappe.datetime.add_days(
			frm.doc.posting_date,
			cint(frm.doc.loan_tenure)
		);

		frm.set_value('loan_due_date', due_date);
	},

	cal_average_forward_rate(frm) {

		const total_forward_rate = frappe.utils.sum(
			(frm.doc.forwards || []).map(function (i) {
				return flt(i.forward_rate) * flt(i.amount_utilized);
			})
		);

		frm.set_value(
			"average_forward_rate",
			flt(total_forward_rate / (frm.doc.total_amount_utilized || 1))
		);
	},

	cal_total_amount_utilized(frm) {

		const total_amount_utilized = frappe.utils.sum(
			(frm.doc.forwards || []).map(function (i) {
				return i.amount_utilized;
			})
		);

		frm.set_value(
			"total_amount_utilized",
			total_amount_utilized
		);
	},
});

frappe.ui.form.on("Forward Utilization", {

	forwards_remove(frm, cdt, cdn) {

		frm.events.cal_average_forward_rate(frm);
		frm.events.cal_total_amount_utilized(frm);
	},

	forward_rate(frm, cdt, cdn) {

		frm.events.cal_average_forward_rate(frm);
	},

	amount_utilized(frm, cdt, cdn) {

		frm.events.cal_total_amount_utilized(frm);
	},
});