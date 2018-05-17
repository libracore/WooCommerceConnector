## ERPNext WooCommerce Connector

WooCommerce connector for ERPNext

This connector allows the synchronisation of items, stock, customers, addresses, sales orders, sales invoices and payment entries to a WooCommerce instance.

It requires the Frappe Framework and [ERPNext](https://erpnext.org).

#### License

AGPL

#### Installation

On the ERPNext server, run

    $ cd /home/frappe/frappe-bench
	$ bench get-app https://github.com/libracore/woocommerceconnector.git
	$ bench install-app woocommerceconnector
