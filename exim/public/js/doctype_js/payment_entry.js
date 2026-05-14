frappe.ui.form.on("Payment Entry", {
	setup(frm) {
		frm.add_fetch("forward_contract", "booking_rate", "forward_rate");
		frm.add_fetch("forward_contract", "amount", "amount");
		frm.add_fetch("forward_contract", "maturity_from", "maturity_from");
		frm.add_fetch("forward_contract", "maturity_to", "maturity_to");
		frm.add_fetch("forward_contract", "amount_outstanding", "amount_outstanding");
		frm.add_fetch("forward_contract", "amount_outstanding", "amount_utilized");

		frm.set_query("forward_contract", "forwards", function () {
			return {
				filters: {
					hedge: "Export",
					status: "Open",
					docstatus: 1,
					amount_outstanding: [">", "0"],
					currency: frm.doc.paid_from_account_currency,
				},
			};
		});
	},

	paid_to(frm) {
		frm.refresh();
	},

	onload(frm) {
		if (frm.doc.__islocal && frm.doc.payment_type === "Pay") {
			frm.set_value("print_heading", "Payment Advice");
		}

		let df = frappe.meta.get_docfield(
			"Forward Utilization",
			"forward_amount",
			frm.doc.name
		);
		df.options = "paid_from_account_currency";

		df = frappe.meta.get_docfield(
			"Forward Utilization",
			"amount_outstanding",
			frm.doc.name
		);
		df.options = "paid_from_account_currency";

		df = frappe.meta.get_docfield(
			"Forward Utilization",
			"amount_utilized",
			frm.doc.name
		);
		df.options = "paid_from_account_currency";

		// Ignore cancellation for all linked documents of respective DocTypes.
		frm.ignore_doctypes_on_cancel_all = ["Forward Booking"];
	},

	validate(frm) {
		if (cstr(frm.doc.forwards)) {
			if (frm.doc.total_amount_utilized !== frm.doc.paid_amount) {
				frappe.throw(
					__("Total Amount Utilized must be same as Paid Amount.")
				);
			}
		}

		frm.trigger("cal_average_forward_rate");
	},

	payment_type(frm) {
		if (frm.doc.payment_type === "Pay") {
			frm.set_value("print_heading", "Payment Advice");
		}

		if (frm.doc.payment_type === "Receive") {
			frm.set_value("print_heading", "Payment Receipt");
		}
	},

	contact_person(frm) {
		erpnext.utils.get_contact_details(frm);
	},

	average_forward_rate(frm) {
		if (frm.doc.average_forward_rate) {
			frm.set_value(
				"source_exchange_rate",
				frm.doc.average_forward_rate
			);
		} else {
			const company_currency = frappe.get_doc(
				":Company",
				frm.doc.company
			).default_currency;

			frm.events.set_current_exchange_rate(
				frm,
				"source_exchange_rate",
				frm.doc.paid_from_account_currency,
				company_currency
			);
		}
	},

	cal_average_forward_rate(frm) {
		let total_forward_amount = 0;
		let total_forward_inr_amount = 0;

		(frm.doc.forwards || []).forEach((row) => {
			total_forward_amount += flt(row.amount_utilized);
			total_forward_inr_amount +=
				flt(row.forward_rate) * flt(row.amount_utilized);
		});

		frm.set_value(
			"average_forward_rate",
			flt(total_forward_inr_amount / (total_forward_amount || 1))
		);
	},

	cal_total_amount_utilized(frm) {
		let total_amount_utilized = 0;

		(frm.doc.forwards || []).forEach((row) => {
			total_amount_utilized += flt(row.amount_utilized);
		});

		frm.set_value("total_amount_utilized", total_amount_utilized);
	},
});

frappe.ui.form.on("Forward Utilization", {
	forwards_remove(frm) {
		frm.events.cal_average_forward_rate(frm);
		frm.events.cal_total_amount_utilized(frm);
	},

	forward_rate(frm) {
		frm.events.cal_average_forward_rate(frm);
	},

	amount_utilized(frm) {
		frm.events.cal_total_amount_utilized(frm);
	},
});