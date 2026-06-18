# -*- coding: utf-8 -*-
"""Settings: konfigurasi Evolution API di res.config.settings.

Akses: Settings > Website > WhatsApp Evolution API Settings
"""

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ============================================================
    # FIELDS
    # ============================================================

    whatsapp_evolution_enabled = fields.Boolean(
        string='Aktifkan WhatsApp Notification',
        config_parameter='whatsapp_evolution.enabled',
        default=True,
        help="Master switch untuk semua notifikasi WA",
    )
    whatsapp_evolution_base_url = fields.Char(
        string='Evolution API URL',
        config_parameter='whatsapp_evolution.base_url',
        default='https://evolution.warunglakku.com',
        help="Base URL Evolution API, contoh: https://evolution.warunglakku.com",
    )
    whatsapp_evolution_instance_name = fields.Char(
        string='Instance Name',
        config_parameter='whatsapp_evolution.instance_name',
        default='Warung Lakku',
        help="Nama instance di Evolution API (lihat di /manager)",
    )
    whatsapp_evolution_api_key = fields.Char(
        string='API Key',
        config_parameter='whatsapp_evolution.api_key',
        help="API key / token instance Evolution API",
    )

    # Per-trigger toggle
    whatsapp_trigger_order_received = fields.Boolean(
        string='Order Diterima (detail + URL)',
        config_parameter='whatsapp_evolution.trigger_order_received',
        default=True,
    )
    whatsapp_trigger_qris_pending = fields.Boolean(
        string='QRIS Menunggu Verifikasi',
        config_parameter='whatsapp_evolution.trigger_qris_pending',
        default=False,
        help="Default OFF untuk hindari spam (admin tetap dapat notif via dashboard)",
    )
    whatsapp_trigger_qris_paid = fields.Boolean(
        string='QRIS Dibayar',
        config_parameter='whatsapp_evolution.trigger_qris_paid',
        default=True,
    )
    whatsapp_trigger_qris_rejected = fields.Boolean(
        string='QRIS Ditolak',
        config_parameter='whatsapp_evolution.trigger_qris_rejected',
        default=True,
    )
    whatsapp_trigger_cod_waiting = fields.Boolean(
        string='COD Siap Dikirim',
        config_parameter='whatsapp_evolution.trigger_cod_waiting',
        default=True,
    )
    whatsapp_trigger_order_delivered = fields.Boolean(
        string='Pesanan Dalam Pengiriman',
        config_parameter='whatsapp_evolution.trigger_order_delivered',
        default=True,
    )
    whatsapp_trigger_order_cooking = fields.Boolean(
        string='Pesanan Sedang Dimasak',
        config_parameter='whatsapp_evolution.trigger_order_cooking',
        default=True,
    )
    whatsapp_trigger_order_done = fields.Boolean(
        string='Pesanan Selesai',
        config_parameter='whatsapp_evolution.trigger_order_done',
        default=True,
    )
    whatsapp_trigger_order_cancelled = fields.Boolean(
        string='Pesanan Dibatalkan',
        config_parameter='whatsapp_evolution.trigger_order_cancelled',
        default=True,
    )

    # Branding URL
    whatsapp_portal_base_url = fields.Char(
        string='Portal URL (Customer)',
        config_parameter='whatsapp_evolution.portal_base_url',
        default='https://odoo.warunglakku.com',
        help="Base URL portal customer, contoh: https://odoo.warunglakku.com",
    )
    whatsapp_store_name = fields.Char(
        string='Nama Toko',
        config_parameter='whatsapp_evolution.store_name',
        default='Warung Lakku',
    )

    # ============================================================
    # ACTIONS
    # ============================================================

    def action_test_connection(self):
        """Test koneksi Evolution API + kirim pesan test ke admin."""
        self.ensure_one()
        client = self.env['whatsapp.evolution.client']
        # Kirim test ke nomor user yang login (kalau punya mobile)
        admin = self.env.user.partner_id
        number = admin.mobile or admin.phone
        if not number:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Test WA gagal',
                    'message': 'User Anda tidak punya nomor mobile/phone. Set di kontak dulu.',
                    'type': 'danger',
                    'sticky': False,
                },
            }
        text = "Test dari Odoo × Evolution API - konfigurasi berhasil. Pesan ini dikirim dari menu Settings > WhatsApp Evolution API."
        log = self.env['whatsapp.message.log'].log_and_send(
            partner_id=admin.id,
            trigger='test',
            message_text=text,
            number_override=number,
        )
        if log.status == 'success':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Test WA sukses',
                    'message': 'Pesan terkirim ke %s (msg_id: %s)' % (log.number_normalized, log.message_id),
                    'type': 'success',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test WA gagal',
                'message': log.error_message or 'Unknown error',
                'type': 'danger',
                'sticky': True,
            },
        }
