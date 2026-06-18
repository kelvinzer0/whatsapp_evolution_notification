# -*- coding: utf-8 -*-
{
    'name': 'WhatsApp Evolution API Notification',
    'version': '17.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Notifikasi WhatsApp otomatis ke customer via Evolution API untuk setiap perubahan status pesanan',
    'description': """
WhatsApp Evolution API Notification
====================================

Modul Odoo 17 untuk kirim notifikasi WhatsApp ke customer otomatis setiap
perubahan status pesanan, menggunakan Evolution API (https://evolution.warunglakku.com).

Trigger yang didukung:
- Order diterima (sale order confirmed) -> kirim DETAIL ORDER + URL portal
- Pembayaran QRIS diterima (admin verify) -> status update biasa
- Pembayaran QRIS ditolak (admin reject) -> status update biasa
- QRIS menunggu verifikasi -> status update biasa (opsional)
- COD siap dikirim -> status update biasa
- Pesanan dikirim (delivered) -> status update biasa
- Pesanan selesai (done) -> status update biasa
- Pesanan dibatalkan (cancelled) -> status update biasa

Pesan "Order diterima" menyertakan:
- Nomor order
- Detail item (nama produk, qty, harga, subtotal)
- Total
- URL portal customer (/my/orders/<id>)

Pesan update status berikutnya hanya:
- Nomor order
- Status baru
- URL portal customer (singkat)

Konfigurasi:
- Settings > Website > WhatsApp Evolution API Settings
- API URL: https://evolution.warunglakku.com
- Instance Name: "Warung Lakku"
- API Key: token instance
- Toggle per trigger (on/off)

Log pesan tersimpan di model whatsapp.message.log (audit trail).

Author: Warung Lakku
""",
    'author': 'Warung Lakku',
    'website': 'https://warunglakku.com',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'website_sale',
        'website_sale_payment_qris_cod',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_retry.xml',
        'views/res_config_settings_views.xml',
        'views/whatsapp_message_log_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
