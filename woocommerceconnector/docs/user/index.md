# ERPNext woocommerce Connector

This app synchronizes the following data between your woocommerce and ERPNext accounts

1. Products
1. Customers
1. Orders, payments and order fulfillment from woocommerce into ERPNext

---

## Setup

1. [Install]({{ docs_base_url }}/index.html#install) ERPNext woocommerce app in your ERPNext site
1. Connect your woocommerce account to ERPNext
	1. Connect via the Public ERPNext App in woocommerce's App Store (recommended)
	1. Connect by creating a Private App
	
#### Connect via the Public ERPNext App

1. Login to your woocommerce account and install [ERPNext app](https://apps.woocommerce.com/erpnext-connector-1) from the woocommerce App Store
1. On installing the app, you will be redirected to **ERPNext woocommerce Connector** page where you will need to fill in your ERPNext credentials and then click on Submit    
    <img class="screenshot" src="{{ docs_base_url }}/assets/img/broker1.2.png">    
1. Next, you will be taken to the Permissions page, where you will be asked to allow ERPNext to:
    - Modify Products, variants and collections
    - Modify Customer details and customer groups
    - Modify Orders, transactions and fulfillments    
	<img class="screenshot" src="{{ docs_base_url }}/assets/img/permission.png">
1. Next, login to your ERPNext site, go to Setup > Integrations > woocommerce Settings and modify the connector's configuration

#### Connect by creating a Private App

1. From within your woocommerce account, go to Apps > Private Apps > Create a Private App
    <img class="screenshot" src="{{ docs_base_url }}/assets/img/woocommerce-private-apps-page.png">
1. Give it a title and save the app. woocommerce will generate a unique API Key and Password for this app
    <img class="screenshot" src="{{ docs_base_url }}/assets/img/woocommerce-new-private-app.png">
1. Login to your ERPNext site, then navigate to Setup > Integrations > woocommerce Settings
1. Select the App Type as "Private", specify your woocommerce account's URL, copy the private app's API Key and Password into the form and save the settings
    <img class="screenshot" src="{{ docs_base_url }}/assets/img/erpnext-config-for-private-app.png">

---

## woocommerce Settings

> Setup > Integrations > woocommerce Settings

1. Specify Price List and Warehouse to be used in the transactions
1. Specify which Cash/Bank Account to use for recording payments
1. Map woocommerce Taxes and Shipping to ERPNext Accounts
1. Mention the Series to be used by the transactions created during sync

<img class="screenshot" src="{{ docs_base_url }}/assets/img/setup-woocommerce-settings.png">

---

## Synchronization

The connector app synchronizes data between woocommerce and ERPNext automatically, every hour. However, you can initiate a manual sync by going to Setup > Integrations > woocommerce Settings and clicking on **Sync woocommerce**

<img class="screenshot" src="{{ docs_base_url }}/assets/img/sync.png">

