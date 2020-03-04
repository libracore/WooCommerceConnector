# -*- coding: utf-8 -*- 
# Copyright (c) 2018, libracore and Contributors 
# See license.txt
from __future__ import unicode_literals

import os
import json
import frappe
import unittest
from frappe.utils import cint, cstr, flt
from frappe.utils.fixtures import sync_fixtures
from woocommerceconnector.sync_orders import create_order, valid_customer_and_product
from woocommerceconnector.sync_products import update_item_stock
from woocommerceconnector.sync_customers import create_customer
from erpnext.stock.utils import get_bin

class WooCommerceSettings(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		sync_fixtures("woocommerceconnector")
		frappe.reload_doctype("Customer")
		frappe.reload_doctype("Sales Order")
		frappe.reload_doctype("Delivery Note")
		frappe.reload_doctype("Sales Invoice")
		
		self.setup_woocommerce()
	
	def setup_woocommerce(self):
		woocommerce_settings = frappe.get_doc("WooCommerce Settings")
		woocommerce_settings.taxes = []
		
		woocommerce_settings.update({
			"app_type": "Private",
			"woocommerce_url": "test.mywoocommerce.com",
			"api_key": "17702c7c4452b9c5d235240b6e7a39da",
			"password": "17702c7c4452b9c5d235240b6e7a39da",
			"price_list": "_Test Price List",
			"warehouse": "_Test Warehouse - _TC",
			"cash_bank_account": "Cash - _TC",
			"customer_group": "_Test Customer Group",
			"taxes": [
				{
					"woocommerce_tax": "International Shipping",
					"tax_account":"Legal Expenses - _TC"
				}
			],
			"enable_woocommerce": 0,
			"sales_order_series": "SO-",
			"sales_invoice_series": "SINV-",
			"delivery_note_series": "DN-"
		}).save(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		
		records = {
			"Sales Invoice": [{"woocommerce_order_id": "2414345735"}],
			"Delivery Note": [{"woocommerce_order_id": "2414345735"}],
			"Sales Order": [{"woocommerce_order_id": "2414345735"}],
			"Item": [{"woocommerce_product_id" :"4059739520"},{"woocommerce_product_id": "13917612359"}, 
				{"woocommerce_product_id": "13917612423"}, {"woocommerce_product_id":"13917612487"}],
			"Address": [{"woocommerce_address_id": "2476804295"}],
			"Customer": [{"woocommerce_customer_id": "2324518599"}]
		}
		
		for doctype in ["Sales Invoice", "Delivery Note", "Sales Order", "Item", "Address", "Customer"]:
			for filters in records[doctype]:
				for record in frappe.get_all(doctype, filters=filters):
					if doctype not in ["Customer", "Item", "Address"]:
						doc = frappe.get_doc(doctype, record.name)
						if doc.docstatus == 1:
							doc.cancel()
					frappe.delete_doc(doctype, record.name)

	def test_product(self):
		with open (os.path.join(os.path.dirname(__file__), "test_data", "woocommerce_item.json")) as woocommerce_item:
			woocommerce_item = json.load(woocommerce_item)

		make_item("_Test Warehouse - _TC", woocommerce_item.get("product"), [])

		item = frappe.get_doc("Item", cstr(woocommerce_item.get("product").get("id")))

		self.assertEqual(cstr(woocommerce_item.get("product").get("id")), item.woocommerce_product_id)
		self.assertEqual(item.sync_with_woocommerce, 1)

		#test variant price
		for variant in woocommerce_item.get("product").get("variants"):
			price = frappe.get_value("Item Price",
				{"price_list": "_Test Price List", "item_code": cstr(variant.get("id"))}, "price_list_rate")
			self.assertEqual(flt(variant.get("price")), flt(price))

	def test_customer(self):
		with open (os.path.join(os.path.dirname(__file__), "test_data", "woocommerce_customer.json")) as woocommerce_customer:
			woocommerce_customer = json.load(woocommerce_customer)

		create_customer(woocommerce_customer.get("customer"), [])

		customer = frappe.get_doc("Customer", {"woocommerce_customer_id": cstr(woocommerce_customer.get("customer").get("id"))})

		self.assertEqual(customer.sync_with_woocommerce, 1)

		woocommerce_address = woocommerce_customer.get("customer").get("addresses")[0]
		address = frappe.get_doc("Address", {"customer": customer.name})

		self.assertEqual(cstr(woocommerce_address.get("id")), address.woocommerce_address_id)
	
	def test_order(self):
		with open (os.path.join(os.path.dirname(__file__), "test_data", "woocommerce_customer.json")) as woocommerce_customer:
			woocommerce_customer = json.load(woocommerce_customer)
			
		create_customer(woocommerce_customer.get("customer"), [])
		
		with open (os.path.join(os.path.dirname(__file__), "test_data", "woocommerce_item.json")) as woocommerce_item:
			woocommerce_item = json.load(woocommerce_item)

		make_item("_Test Warehouse - _TC", woocommerce_item.get("product"), [])
				
		with open (os.path.join(os.path.dirname(__file__), "test_data", "woocommerce_order.json")) as woocommerce_order:
			woocommerce_order = json.load(woocommerce_order)

		woocommerce_settings = frappe.get_doc("WooCommerce Settings", "WooCommerce Settings")
		
		create_order(woocommerce_order.get("order"), woocommerce_settings, "_Test Company")

		sales_order = frappe.get_doc("Sales Order", {"woocommerce_order_id": cstr(woocommerce_order.get("order").get("id"))})

		self.assertEqual(cstr(woocommerce_order.get("order").get("id")), sales_order.woocommerce_order_id)

		#check for customer
		woocommerce_order_customer_id = cstr(woocommerce_order.get("order").get("customer").get("id"))
		sales_order_customer_id = frappe.get_value("Customer", sales_order.customer, "woocommerce_customer_id")

		self.assertEqual(woocommerce_order_customer_id, sales_order_customer_id)

		#check sales invoice
		sales_invoice = frappe.get_doc("Sales Invoice", {"woocommerce_order_id": sales_order.woocommerce_order_id})
		self.assertEqual(sales_invoice.rounded_total, sales_order.rounded_total)

		#check delivery note
		delivery_note_count = frappe.db.sql("""select count(*) from `tabDelivery Note`
			where woocommerce_order_id = %s""", sales_order.woocommerce_order_id)[0][0]

		self.assertEqual(delivery_note_count, len(woocommerce_order.get("order").get("fulfillments")))

def test_bin(item_code, warehouse):
    bin = get_bin(item_code, warehouse)
    print("{0} has {1} of {2}".format(warehouse, bin.actual_qty, item_code))
    return 

def test_multibin(item_code, warehouse):
    woocommerce_settings = frappe.get_doc("WooCommerce Settings", "WooCommerce Settings")
    bin = get_bin(item_code, woocommerce_settings.warehouse)
    qty = bin.actual_qty
    for warehouse in woocommerce_settings.warehouses:
        _bin = get_bin(item_code, warehouse.warehouse)
        qty += _bin.actual_qty
    print("Multi-warehouses have {1} of {2}".format(warehouse, qty, item_code))
    return

def test_update_item_stock(item_code):
    woocommerce_settings = frappe.get_doc("WooCommerce Settings", "WooCommerce Settings")
    update_item_stock(item_code, woocommerce_settings)
    print("Updated {0}".format(item_code))
    return
