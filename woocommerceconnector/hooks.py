# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "erpnext_woocommerce"
app_title = "ERPNext woocommerce"
app_publisher = "Frappe Technologies Pvt. Ltd."
app_description = "woocommerce connector for ERPNext"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "info@frappe.io"
app_license = "MIT"

fixtures = ["Custom Field"]
# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/erpnext_woocommerce/css/erpnext_woocommerce.css"
# app_include_js = "/assets/erpnext_woocommerce/js/erpnext_woocommerce.js"

# include js, css files in header of web template
# web_include_css = "/assets/erpnext_woocommerce/css/erpnext_woocommerce.css"
# web_include_js = "/assets/erpnext_woocommerce/js/erpnext_woocommerce.js"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "erpnext_woocommerce.install.before_install"
after_install = "erpnext_woocommerce.after_install.create_weight_uom"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erpnext_woocommerce.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Bin": {
		"on_update": "erpnext_woocommerce.sync_products.trigger_update_item_stock"
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly": [
		"erpnext_woocommerce.api.sync_woocommerce"
	]
}

# Testing
# -------

# before_tests = "erpnext_woocommerce.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "erpnext_woocommerce.event.get_events"
# }

