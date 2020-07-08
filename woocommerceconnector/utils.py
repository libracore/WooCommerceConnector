# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from .exceptions import woocommerceSetupError

def disable_woocommerce_sync_for_item(item, rollback=False):
	"""Disable Item if not exist on woocommerce"""
	if rollback:
		frappe.db.rollback()
		
	item.sync_with_woocommerce = 0
	item.sync_qty_with_woocommerce = 0
	item.save(ignore_permissions=True)
	frappe.db.commit()

def disable_woocommerce_sync_on_exception():
	frappe.db.rollback()
	frappe.db.set_value("woocommerce Settings", None, "enable_woocommerce", 0)
	frappe.db.commit()

def is_woocommerce_enabled():
	woocommerce_settings = frappe.get_doc("woocommerce Settings")
	if not woocommerce_settings.enable_woocommerce:
		return False
	try:
		woocommerce_settings.validate()
	except woocommerceSetupError:
		return False
	
	return True
	
def make_woocommerce_log(title="Sync Log", status="Queued", method="sync_woocommerce", message=None, exception=False, 
name=None, request_data={}):
	if not name:
		name = frappe.db.get_value("woocommerce Log", {"status": "Queued"})
		
		if name:
			""" if name not provided by log calling method then fetch existing queued state log"""
			log = frappe.get_doc("woocommerce Log", name)
		
		else:
			""" if queued job is not found create a new one."""
			log = frappe.get_doc({"doctype":"woocommerce Log"}).insert(ignore_permissions=True)
		
		if exception:
			frappe.db.rollback()
			log = frappe.get_doc({"doctype":"woocommerce Log"}).insert(ignore_permissions=True)
			
		log.message = message if message else frappe.get_traceback()
		log.title = (title or "-")[0:140]
		log.method = method
		log.status = status
		log.request_data= json.dumps(request_data)
		
		log.save(ignore_permissions=True)
		frappe.db.commit()
