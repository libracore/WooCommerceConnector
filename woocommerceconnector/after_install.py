# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def create_weight_uom():
	for unit in ['g', 'kg', 'lbs', 'oz']:
		if not frappe.db.get_value("UOM", unit.title(), "name"):
			uom = frappe.new_doc("UOM")
			uom.uom_name = unit.title()
			uom.insert(ignore_permissions=True)