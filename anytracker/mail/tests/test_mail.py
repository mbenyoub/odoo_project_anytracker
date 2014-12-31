# coding: utf-8
from anybox.testing.openerp import SharedSetupTransactionCase


class TestMail(SharedSetupTransactionCase):

    _module_ns = 'anytracker'

    def test_reply_to_email_anytracker(self):
        cr, uid = self.cr, self.uid
        mail = self.registry('mail.mail')
        mail_message = self.registry('mail.message')
        message_id = mail_message.create(
            cr, uid,
            {'model': 'anytracker.ticket', 'body': '<p> Test </p>', 'record_name': 'Test',
             'type': 'comment', 'author_id': 1, 'res_id': 1})
        mail_id = mail.create(
            cr, uid,
            {'mail_message_id': message_id, 'references': 'test', 'reply_to': 'admin@example',
             'auto_delete': 'True', 'body_html': '<p> Test </p>',
             'email_from': u'Administrator <admin@example.com>'})
        self.assertEquals(mail.browse(cr, uid, mail_id).reply_to, 'anytracker@anybox.fr')
