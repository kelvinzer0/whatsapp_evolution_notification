# -*- coding: utf-8 -*-
{
    'name': 'WhatsApp Evolution API Notification',
    'version': '17.0.1.2.0',
    'category': 'Website/Website',
    'summary': 'Notifikasi WhatsApp otomatis ke customer via Evolution API untuk setiap perubahan status pesanan',
    'description': """
WhatsApp Evolution API Notification
====================================

Modul Odoo 17 untuk kirim notifikasi WhatsApp ke customer otomatis setiap
perubahan status pesanan, menggunakan Evolution API (https://evolution.warunglakku.com).

Trigger yang didukung (dengan emoji prefix):
- 🛒 Order diterima (sale order confirmed) -> kirim DETAIL ORDER + URL portal
- ⏳ QRIS menunggu verifikasi -> status update (opsional, default OFF)
- ✅ Pembayaran QRIS diterima (admin verify) -> status update biasa
- ❌ Pembayaran QRIS ditolak (admin reject) -> status update + alasan
- 📦 COD siap dikirim -> status update biasa
- 🚚 Pesanan dikirim (website_order_stage -> out_for_delivery) -> status update
- ✅ Pesanan selesai (done) -> status update biasa
- ❌ Pesanan dibatalkan (cancelled) -> status update biasa

Format pesan: TO-THE-POINT, no greeting (langsung ke isi).
Emoji prefix memudahkan customer mengenali jenis update.

Pesan "Order diterima" menyertakan:
- Nomor order
- Detail item (nama produk, qty, harga, subtotal)
- Total
- URL halaman public read-only untuk detail pesanan

Pesan update status berikutnya sangat singkat:
- Emoji + status + nomor order
- (Tidak ada URL di pesan update — customer sudah punya link dari notif pertama)

Halaman public read-only: /shop/order/<order_id>/<access_token>
- Akses tanpa login
- Hanya view (tidak ada action/edit)
- Token di-generate otomatis per order (field access_token bawaan website_sale)

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
        'views/public_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
