# -*- coding: utf-8 -*-
from openerp.report import report_sxw
from .CommonParser import CommonParser


class BouquetReport(CommonParser):
    def __init__(self, cr, uid, name, context):
        super(BouquetReport, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({'test_methode': self._test_methode,
                                  })

    def _test_methode(self):
        return True

report_sxw.report_sxw('report.bouquet_webkit',
                      'anytracker.bouquet',
                      'anytracker_report/webkit_report/bouquet.mako',
                      parser=BouquetReport)
