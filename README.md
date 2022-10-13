ERPNext WooCommerce Connector
WooCommerce connector app for ERPNext. This connector allows  synchronisation of items, stock, customers, addresses, sales orders, sales invoices and payment entries between WooCommerce instance & ERPNext. It requires the Frappe Framework and ERPNext (https://erpnext.com/).

#### License AGPL

#### Installation
SSH into ERPNext server and follow below commands
    $ cd /home/frappe/frappe-bench
	$ bench get-app https://github.com/muzzy73/woocommerceconnector.git
	$ bench install-app woocommerceconnector
	$ bench migrate
	$ bench clear-cache
