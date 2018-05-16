from __future__ import unicode_literals
import frappe

class woocommerceError(frappe.ValidationError): pass
class woocommerceSetupError(frappe.ValidationError): pass
