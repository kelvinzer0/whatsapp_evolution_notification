# -*- coding: utf-8 -*-
"""Helper client untuk kirim WhatsApp via Evolution API.

Format endpoint (Evolution API v2.x):
    POST {base_url}/message/sendText/{instance_name}
    Header: apikey: {api_key}
    Body: {"number": "62xxx", "text": "...", "delay": 1200}

Response sukses berisi:
    {"key": {"remoteJid": "...", "fromMe": true, "id": "..."}, "status": "PENDING", ...}
"""

import json
import logging
import re
import requests
from werkzeug.urls import url_join

from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Default timeout untuk request ke Evolution API
DEFAULT_TIMEOUT = 20  # detik
DEFAULT_DELAY = 1200  # ms jeda antar pesan (rate limit WhatsApp)


class WhatsappEvolutionClient(models.Model):
    """Helper service untuk kirim WA via Evolution API.

    Model tanpa table (_auto=False) — dipakai sebagai service singleton
    via self.env['whatsapp.evolution.client'].send_text(...)
    """
    _name = 'whatsapp.evolution.client'
    _description = 'WhatsApp Evolution API Client Service'
    _auto = False  # tidak buat table di DB

    # ============================================================
    # PUBLIC API
    # ============================================================

    def send_text(self, number_raw, text, retry_on_fail=True):
        """Kirim pesan teks WA ke nomor tujuan.

        :param number_raw: nomor HP tujuan (bebas format: 08xxx, +62xxx, dst)
        :param text: isi pesan
        :param retry_on_fail: jika True, simpan ke log dengan status 'failed'
                              untuk di-retry oleh cron
        :return: dict {success: bool, message_id: str|False, raw: dict, error: str}
        """
        # NOTE: AbstractModel — no ensure_one() since called as self.env[...]
        config = self._get_config()
        if not config.get('enabled'):
            _logger.info("[WA] Disabled, skip send to %s", number_raw)
            return {'success': False, 'message_id': False, 'raw': {},
                    'error': 'WhatsApp notification disabled'}

        number = self._normalize_number(number_raw)
        if not number:
            _logger.warning("[WA] Invalid number: %s", number_raw)
            return {'success': False, 'message_id': False, 'raw': {},
                    'error': 'Invalid number: %s' % number_raw}

        if not text or not text.strip():
            return {'success': False, 'message_id': False, 'raw': {},
                    'error': 'Empty message text'}

        result = self._do_send(config, number, text)
        return result

    # ============================================================
    # INTERNAL
    # ============================================================

    def _get_config(self):
        """Ambil konfigurasi dari res.config.settings (singleton)."""
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'enabled': ICP.get_param('whatsapp_evolution.enabled', 'True') == 'True',
            'base_url': (ICP.get_param('whatsapp_evolution.base_url') or '').rstrip('/'),
            'instance_name': ICP.get_param('whatsapp_evolution.instance_name') or '',
            'api_key': ICP.get_param('whatsapp_evolution.api_key') or '',
        }

    def _normalize_number(self, number):
        """Normalisasi nomor HP ke format internasional Indonesia (62xxx).

        Aturan:
        - Buang karakter non-digit (+, spasi, -, dll)
        - Ganti prefix 0 di depan dengan 62
        - Jika sudah 62xxx, biarkan
        - Jika <10 digit atau >15 digit, anggap invalid

        :return: str normalisasi ATAU '' jika invalid
        """
        if not number:
            return ''
        digits = re.sub(r'\D', '', str(number))
        if not digits:
            return ''
        # Indonesia: prefix 0 -> 62
        if digits.startswith('0'):
            digits = '62' + digits[1:]
        elif digits.startswith('62'):
            pass  # already correct
        elif digits.startswith('8') and len(digits) >= 9:
            # 08xxx tapi 0 hilang, prepend 62
            digits = '62' + digits
        # Validate length
        if len(digits) < 9 or len(digits) > 15:
            return ''
        return digits

    def _do_send(self, config, number, text):
        """Eksekusi HTTP request ke Evolution API."""
        base_url = config.get('base_url')
        instance = config.get('instance_name')
        api_key = config.get('api_key')

        if not (base_url and instance and api_key):
            _logger.warning("[WA] Incomplete config: base_url=%s, instance=%s, key=%s",
                            base_url, instance, '***' if api_key else 'EMPTY')
            return {'success': False, 'message_id': False, 'raw': {},
                    'error': 'Incomplete Evolution API config'}

        # URL-encode instance name (untuk kasus "Warung Lakku" ada spasi)
        from urllib.parse import quote
        instance_encoded = quote(instance, safe='')
        endpoint = url_join(base_url + '/', 'message/sendText/%s' % instance_encoded)

        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json',
        }
        payload = {
            'number': number,
            'text': text,
            'delay': DEFAULT_DELAY,
        }

        try:
            resp = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.exceptions.Timeout:
            _logger.error("[WA] Timeout sending to %s via %s", number, endpoint)
            return {'success': False, 'message_id': False, 'raw': {},
                    'error': 'Request timeout'}
        except requests.exceptions.RequestException as e:
            _logger.error("[WA] Request error to %s: %s", number, e)
            return {'success': False, 'message_id': False, 'raw': {},
                    'error': 'Request error: %s' % e}

        # Parse response
        try:
            raw = resp.json()
        except Exception:
            raw = {'raw_text': resp.text[:500]}

        if resp.status_code == 200 or resp.status_code == 201:
            # Success — extract message ID
            key = raw.get('key', {}) if isinstance(raw, dict) else {}
            msg_id = key.get('id', '') if isinstance(key, dict) else ''
            status = raw.get('status', '') if isinstance(raw, dict) else ''
            _logger.info("[WA] Sent to %s (msg_id=%s, status=%s)",
                         number, msg_id, status)
            return {'success': True, 'message_id': msg_id, 'raw': raw, 'error': ''}

        _logger.error("[WA] Failed send to %s: HTTP %s - %s",
                      number, resp.status_code, str(raw)[:300])
        return {
            'success': False,
            'message_id': False,
            'raw': raw,
            'error': 'HTTP %s: %s' % (resp.status_code, str(raw)[:200]),
        }
