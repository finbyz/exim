// Copyright (c) 2026, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

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
			fieldname: "from_date",
			label: __("From Date (ETA)"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		},
		{
			fieldname: "to_date",
			label: __("To Date (ETA)"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "import_shipment",
			label: __("Import Shipment"),
			fieldtype: "Link",
			options: "Import Shipment",
			get_query: () => {
				const company = frappe.query_report.get_filter_value("company");
				return { filters: company ? { company } : {} };
			},
		},
		{
			fieldname: "container",
			label: __("Container"),
			fieldtype: "Link",
			options: "Container",
		},
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: ["Shipment", "Container"],
			default: "Shipment",
		},
		{
			fieldname: "show_batches",
			label: __("Show Batches"),
			fieldtype: "Check",
			default: 0,
		},
	],

	tree: true,
	name_field: "row_id",
	parent_field: "parent_row",
	initial_depth: 1,

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		if (["profit", "profit_pct"].includes(column.fieldname) && data.profit) {
			const color = data.profit < 0 ? "var(--red-600)" : "var(--green-600)";
			value = `<span style="color:${color}">${value}</span>`;
		}
		if (column.fieldname === "status" && data.status) {
			const colors = {
				Closed: "green",
				"Partly Sold": "orange",
				"In Stock": "blue",
				"Not Received": "gray",
			};
			const color = colors[data.status] || "gray";
			value = `<span class="indicator-pill ${color}">${value}</span>`;
		}
		if (data.indent === 0) {
			value = `<b>${value}</b>`;
		}
		return value;
	},
};
