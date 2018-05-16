# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "woocommerceconnector"
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
# app_include_css = "/assets/woocommerceconnector/css/woocommerceconnector.css"
# app_include_js = "/assets/woocommerceconnector/js/woocommerceconnector.js"

# include js, css files in header of web template
# web_include_css = "/assets/woocommerceconnector/css/woocommerceconnector.css"
# web_include_js = "/assets/woocommerceconnector/js/woocommerceconnector.js"

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

# before_install = "woocommerceconnector.install.before_install"
after_install = "woocommerceconnector.after_install.create_weight_uom"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "woocommerceconnector.notifications.get_notification_config"

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
		"on_update": "woocommerceconnector.sync_products.trigger_update_item_stock"
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly": [
		"woocommerceconnector.api.sync_woocommerce"
	]
}

# Testing
# -------

# before_tests = "woocommerceconnector.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "woocommerceconnector.event.get_events"
# }

