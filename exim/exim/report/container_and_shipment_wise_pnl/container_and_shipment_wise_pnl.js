// Copyright (c) 2026, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

const PNL_METHOD =
	"exim.exim.report.container_and_shipment_wise_pnl.container_and_shipment_wise_pnl.container_query";

frappe.query_reports["Container and Shipment Wise PNL"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "view",
			label: __("View"),
			fieldtype: "Select",
			options: ["Shipment Wise", "Container Wise"],
			default: "Shipment Wise",
			reqd: 1,
			on_change: () => {
				// a container picked in Container Wise means nothing in Shipment Wise
				if (frappe.query_report.get_filter_value("view") !== "Container Wise") {
					frappe.query_report.set_filter_value("container", "");
				} else {
					frappe.query_report.refresh();
				}
			},
		},
		{
			fieldname: "import_shipment",
			label: __("Import Shipment"),
			fieldtype: "Link",
			options: "Import Shipment",
			depends_on: "eval:doc.view",
			get_query: () => {
				const company = frappe.query_report.get_filter_value("company");
				return { filters: Object.assign({ status: ["!=", "Cancelled"] }, company ? { company } : {}) };
			},
			on_change: () => {
				// keep the container only if it belongs to the newly picked shipment
				frappe.query_report.set_filter_value("container", "");
			},
		},
		{
			fieldname: "container",
			label: __("Container"),
			fieldtype: "Link",
			options: "Container",
			depends_on: "eval:doc.view == 'Container Wise'",
			get_query: () => ({
				query: PNL_METHOD,
				filters: {
					company: frappe.query_report.get_filter_value("company"),
					import_shipment: frappe.query_report.get_filter_value("import_shipment"),
				},
			}),
		},
		{
			fieldname: "from_date",
			label: __("From Date (ETA)"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
			depends_on: "eval:!doc.import_shipment && !doc.container",
		},
		{
			fieldname: "to_date",
			label: __("To Date (ETA)"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			depends_on: "eval:!doc.import_shipment && !doc.container",
		},
		{
			fieldname: "show_batches",
			label: __("Show Batches"),
			fieldtype: "Check",
			default: 0,
		},
	],

	// T format as a tree: each container / shipment block collapses to its title, and each group row
	// (Purchase | Sales, Shipment Expenses | Closing Stock, Key Figures) collapses to its totals.
	tree: true,
	name_field: "row_id",
	parent_field: "parent_row",
	initial_depth: 2,

	formatter(value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);
		const f = column.fieldname;
		const prefix = f === "expense" || f.startsWith("e_") ? "e" : "i";
		const is_label = f === "expense" || f === "income";

		if (data.row_type === "gap") return "";
		if (data.row_type === "title") {
			return is_label ? `<b style="font-size:var(--text-md)">${frappe.utils.escape_html(value || "")}</b>` : "";
		}
		if (data.row_type === "side_head") {
			return is_label
				? `<b style="text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">${value}</b>`
				: "";
		}

		const label = prefix === "e" ? data.expense : data.income;
		if (label === undefined || label === null) return "";
		if (!is_label && (value === null || value === undefined)) return "";

		value = default_formatter(value, row, column, data);
		if (is_label && data[`${prefix}_sub`]) {
			value = `<span style="padding-left:16px;color:var(--text-muted)">${value}</span>`;
		}
		// the right-hand label is not the tree column, so indent it by hand like the left one
		if (f === "income" && data.indent === 2) value = `<span style="padding-left:20px">${value}</span>`;

		const kind = data[`${prefix}_kind`];
		if (kind === "profit") value = `<span style="color:var(--green-600)">${value}</span>`;
		if (kind === "loss") value = `<span style="color:var(--red-600)">${value}</span>`;
		if (data[`${prefix}_bold`] || data.row_type === "total") value = `<b>${value}</b>`;
		if (data.row_type === "total") value = `<span style="border-top:1px solid var(--text-color);display:block">${value}</span>`;
		return value;
	},
};
