from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Settings"),
			"icon": "fa fa-building",
			"items": [
				{
					"type": "doctype",
					"name": "WooCommerce Config",
					"label": _("WooCommerce Config"),
					"description": _("Settings"),
				},
			]
		},
		{
			"label": _("Logs"),
			"icon": "fa fa-building",
			"items": [
				{
					"type": "doctype",
					"name": "woocommerce Log",
					"label": _("Sync Logs"),
					"description": _("Sync Logs"),
				}
			]
		}
	]
