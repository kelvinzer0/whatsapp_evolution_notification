# -*- coding: utf-8 -*-
{
    'name': 'WhatsApp Evolution API Notification',
    'version': '17.0.1.3.0',
    'category': 'Website/Website',
    'summary': 'Notifikasi WhatsApp otomatis ke customer via Evolution API untuk setiap perubahan status pesanan',
    'description': """
WhatsApp Evolution API Notification
====================================

Modul Odoo 17 untuk kirim notifikasi WhatsApp ke customer otomatis setiap
perubahan status pesanan, menggunakan Evolution API (https://evolution.warunglakku.com).

Format pesan: PREMIUM, no emoji, clean modern look.
Menggunakan WhatsApp markdown *bold* untuk emphasis.
To-the-point, no greeting, langsung ke isi.

Alur trigger (proses restoran/warung makan):
- *Order Diterima*  (sale confirmed) -> kirim DETAIL ORDER + URL portal
  Format: header PESANAN DITERIMA + No. Order + Tanggal + Metode + Item + Total + URL
- *Pembayaran QRIS Menunggu Verifikasi*  (opsional, default OFF)
- *Pembayaran QRIS Diterima*  (admin verify)
- *Pembayaran QRIS Ditolak*  (admin reject) + Alasan
- *Pesanan Siap Dikirim*  (COD tx created)
- *Pesanan Sedang Dimasak*  (website_order_stage -> cooking)
- *Pesanan Dalam Pengiriman*  (website_order_stage -> out_for_delivery)
- *Pesanan Selesai*  (state -> done) + "Terima kasih telah memesan di {store}."
- *Pesanan Dibatalkan*  (state -> cancelled)

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
