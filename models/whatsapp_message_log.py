# -*- coding: utf-8 -*-
"""Model: whatsapp.message.log

Audit trail semua notifikasi WA yang dikirim (atau gagal) ke customer.
Bisa dipakai untuk:
- Troubleshoot pesan yang gagal
- Retry pesan failed via cron
- Statistik pengiriman
"""

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class WhatsappMessageLog(models.Model):
    _name = 'whatsapp.message.log'
    _description = 'WhatsApp Message Log'
    _order = 'create_date DESC'
    _rec_name = 'create_date'

    # ============================================================
    # FIELDS
    # ============================================================

    partner_id = fields.Many2one('res.partner', string='Customer', ondelete='set null',
                                 help="Penerima pesan")
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', ondelete='set null',
                                    help="Order terkait")
    payment_transaction_id = fields.Many2one('payment.transaction',
                                              string='Payment Transaction',
                                              ondelete='set null',
                                              help="Transaksi pembayaran terkait")

    trigger = fields.Selection([
        ('order_received', 'Order Diterima'),
        ('order_cooking', 'Pesanan Sedang Dimasak'),
        ('order_delivered', 'Pesanan Dalam Pengiriman'),
        ('order_ready_for_pickup', 'Pesanan Siap Diambil'),
        ('order_done', 'Pesanan Selesai'),
        ('order_cancelled', 'Pesanan Dibatalkan'),
        ('qris_pending_verification', 'QRIS Menunggu Verifikasi'),
        ('qris_paid', 'QRIS Dibayar'),
        ('qris_rejected', 'QRIS Ditolak'),
        ('cod_waiting_delivery', 'COD Siap Dikirim'),
        ('test', 'Test Message'),
        ('other', 'Other'),
    ], string='Trigger', required=True, default='other')

    number_raw = fields.Char(string='Nomor Asli', help="Nomor sebelum dinormalisasi")
    number_normalized = fields.Char(string='Nomor Normalisasi',
                                    help="Format internasional 62xxx")
    message_text = fields.Text(string='Isi Pesan')
    message_id = fields.Char(string='Evolution Message ID',
                             help="ID dari Evolution API (untuk tracking)")
    status = fields.Selection([
        ('success', 'Sukses'),
        ('failed', 'Gagal'),
        ('pending', 'Pending'),
    ], string='Status', default='pending', required=True, index=True)
    error_message = fields.Text(string='Error')
    response_raw = fields.Text(string='Raw Response')

    # Retry tracking
    retry_count = fields.Integer(string='Retry Count', default=0)
    last_retry_at = fields.Datetime(string='Last Retry At')

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company,
                                 required=True)

    # ============================================================
    # CRUD
    # ============================================================

    @api.model_create_multi
    def create(self, vals_list):
        logs = super().create(vals_list)
        return logs

    # ============================================================
    # PUBLIC API
    # ============================================================

    @api.model
    def log_and_send(self, partner_id, trigger, message_text, sale_order_id=False,
                     payment_transaction_id=False, number_override=False):
        """Buat log entry lalu kirim pesan via Evolution API.

        :return: log record (sudah dengan status success/failed)
        """
        client = self.env['whatsapp.evolution.client']

        # Tentukan nomor tujuan
        number_raw = number_override
        if not number_raw and partner_id:
            partner = self.env['res.partner'].browse(partner_id)
            number_raw = partner.mobile or partner.phone or ''

        number_normalized = client._normalize_number(number_raw)

        log = self.create({
            'partner_id': partner_id or False,
            'sale_order_id': sale_order_id or False,
            'payment_transaction_id': payment_transaction_id or False,
            'trigger': trigger,
            'number_raw': number_raw,
            'number_normalized': number_normalized,
            'message_text': message_text,
            'status': 'pending',
        })

        if not number_normalized:
            log.write({
                'status': 'failed',
                'error_message': 'Nomor tujuan tidak valid atau kosong',
            })
            _logger.warning("[WA-LOG] Skip send: invalid number for partner_id=%s",
                            partner_id)
            return log

        # Kirim
        result = client.send_text(number_raw, message_text)
        if result.get('success'):
            log.write({
                'status': 'success',
                'message_id': result.get('message_id', ''),
                'response_raw': str(result.get('raw', ''))[:2000],
            })
        else:
            log.write({
                'status': 'failed',
                'error_message': result.get('error', 'Unknown error'),
                'response_raw': str(result.get('raw', ''))[:2000],
            })
        return log

    def retry(self):
        """Retry manual dari UI untuk log yang failed."""
        for log in self:
            if log.status != 'failed':
                continue
            client = self.env['whatsapp.evolution.client']
            result = client.send_text(log.number_raw, log.message_text)
            new_status = 'success' if result.get('success') else 'failed'
            log.write({
                'status': new_status,
                'message_id': result.get('message_id') or log.message_id,
                'error_message': result.get('error', '') if new_status == 'failed' else '',
                'response_raw': str(result.get('raw', ''))[:2000],
                'retry_count': log.retry_count + 1,
                'last_retry_at': fields.Datetime.now(),
            })
        return True

    # ============================================================
    # CRON
    # ============================================================

    @api.model
    def _cron_retry_failed(self, max_retry=3, batch_size=50):
        """Cron: retry log failed yang retry_count < max_retry."""
        logs = self.search([
            ('status', '=', 'failed'),
            ('retry_count', '<', max_retry),
        ], limit=batch_size, order='create_date ASC')
        if not logs:
            return
        _logger.info("[WA-CRON] Retrying %d failed logs", len(logs))
        logs.retry()

    @api.model
    def _cron_cleanup_old_logs(self, days=90):
        """Hapus log berusia > 90 hari untuk hemat storage."""
        from datetime import timedelta
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old_logs = self.search([('create_date', '<', cutoff)])
        if old_logs:
            _logger.info("[WA-CRON] Cleaning up %d old logs (>=%d days)",
                         len(old_logs), days)
            old_logs.unlink()
