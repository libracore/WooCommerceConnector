from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Integrations"),
			"icon": "icon-star",
			"items": [
				{
					"type": "doctype",
					"name": "woocommerce Settings",
					"description": _("Connect woocommerce with ERPNext"),
					"hide_count": True
				}
			]
		}
	]
