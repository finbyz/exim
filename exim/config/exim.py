from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Contact Term"),
			"items": [
				{
					"type": "doctype",
					"name": "Contract Term",
				},
			]
		},
		{
			"label": _("Authorisation License"),
			"items": [
				{
					"type": "doctype",
					"name": "Advance Authorisation License",
				},
			]
		},
		{
			"label": _("Documents"),
			"items": [
				{
					"type": "doctype",
					"name": "Export Document",
				},
				{
					"type": "doctype",
					"name": "Document Paper",
				},
				{
					"type": "doctype",
					"name": "Document Check",
				},
				{
					"type": "doctype",
					"name": "Document Expiry",
				},
				{
					"type": "doctype",
					"name": "Range and Division",
				},
			]
		},
	]