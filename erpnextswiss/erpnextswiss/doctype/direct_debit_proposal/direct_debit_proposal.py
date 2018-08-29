# -*- coding: utf-8 -*-
# Copyright (c) 2018, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from datetime import datetime

class DirectDebitProposal(Document):
    def on_submit(self):
        # create the aggregated payment table
        # collect customers
        customers = []
        for sales_invoice in self.sales_invoices:
            if sales_invoice.customer not in customers:
                customers.append(sales_invoice.customer)
        # aggregate sales invoices
        for customer in customers:
            amount = 0
            references = []
            for sales_invoice in self.sales_invoices:
                if sales_invoice.customer == customer:
                    amount += sales_invoice.amount
                    references.append(sales_invoice.sales_invoice)
                    # mark sales invoices as proposed
                    invoice = frappe.get_doc("Sales Invoice", sales_invoice.sales_invoice)
                    invoice.is_proposed = 1
                    invoice.save()
            # add new payment record
            new_payment = self.append('payments', {})
            new_payment.customer = customer
            new_payment.amount = amount
            new_payment.reference = " ".join(references)

        # save
        self.save()
    
    def create_bank_file(self):
        # create xml header
        content = make_line("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
        # define xml template reference
        content += make_line("<Document xmlns=\"http://www.six-interbank-clearing.com/de/pain.008.001.03.ch.02.xsd\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.six-interbank-clearing.com/de/pain.008.001.03.ch.02.xsd  pain.008.001.03.ch.02.xsd\">")
        # transaction holder
        content += make_line("  <CstmrDrctDbtInitn>")
        ### Group Header (GrpHdr, A-Level)
        # create group header
        content += make_line("    <GrpHdr>")
        # message ID (unique, SWIFT-characters only)
        content += make_line("      <MsgId>MSG-" + time.strftime("%Y%m%d%H%M%S") + "</MsgId>")
        # creation date and time ( e.g. 2010-02-15T07:30:00 )
        content += make_line("      <CreDtTm>" + time.strftime("%Y-%m-%dT%H:%M:%S") + "</CreDtTm>")
        # number of transactions in the file
        transaction_count = 0
        transaction_count_identifier = "<!-- $COUNT -->"
        content += make_line("      <NbOfTxs>" + transaction_count_identifier + "</NbOfTxs>")
        # total amount of all transactions ( e.g. 15850.00 )  (sum of all amounts)
        control_sum = 0.0
        control_sum_identifier = "<!-- $CONTROL_SUM -->"
        content += make_line("      <CtrlSum>" + control_sum_identifier + "</CtrlSum>")
        # initiating party requires at least name or identification
        content += make_line("      <InitgPty>")
        # initiating party name ( e.g. MUSTER AG )
        content += make_line("        <Nm>" + get_company_name(self.sales_invoices[0].sales_invoice) + "</Nm>")
        content += make_line("      </InitgPty>")
        content += make_line("    </GrpHdr>")
        
        ### level B
        company_account = frappe.get_doc('Account', self.receive_to_account)
        content += make_line("    <PmtInf>")
        content += make_line("<PmtInfId>{0}</PmtInfId>".format(self.name))
        content += make_line("<PmtMtd>DD</PmtMtd>")
        content += make_line("<PmtTpInf>")
        content += make_line("<SvcLvl>")
        content += make_line("  <Cd>SEPA</Cd>")
        content += make_line("</SvcLvl>")
        content += make_line("<LclInstrm>")
        content += make_line("  <Cd>CORE</Cd>")
        content += make_line("</LclInstrm>")
        content += make_line("<SeqTp>RCUR</SeqTp>")
        content += make_line("</PmtTpInf>")
        content += make_line("<ReqdColltnDt>{0}</ReqdColltnDt>".format(self.date))
        content += make_line("<Cdtr>")
        content += make_line("<Nm>Fink Zeitsysteme GmbH</Nm>")
        content += make_line("</Cdtr>")
        content += make_line("<CdtrAcct>")
        content += make_line("<Id>")
        content += make_line("  <IBAN>{0}</IBAN>".format(company_account.iban))
        content += make_line("</Id>")
        content += make_line("</CdtrAcct>")
        content += make_line("<CdtrAgt>")
        content += make_line("<FinInstnId>")
        content += make_line("  <BIC>{0}</BIC>".format(company_account.bic))
        content += make_line("</FinInstnId>")
        content += make_line("</CdtrAgt>")
        content += make_line("<ChrgBr>SLEV</ChrgBr>")
        
        # payments
        for payment in self.payments:
            transaction_count += 1
            content += make_line("<DrctDbtTxInf>")
            content += make_line("<PmtId>")
            content += make_line("  <InstrId>SEPA1-{0}-{1}</InstrId>".format(self.date, transaction_count))
            content += make_line("  <EndToEndId>{0}-{1}</EndToEndId>".format(self.name, transaction_count)"
            content += make_line("</PmtId>")
            content += make_line("<InstdAmt Ccy="{0}">{1}</InstdAmt>".format(payment.currency, payment.amount))
            content += make_line("        <DrctDbtTx>")
            content += make_line("  <MndtRltdInf>")
            content += make_line("    <MndtId>{0}_{1}</MndtId>".format(customer.lsv_code)) ## TODO ???
            content += make_line("    <DtOfSgntr>{0}</DtOfSgntr>".format(customer.lsv_date)) ## TODO ??
            content += make_line("    <AmdmntInd>false</AmdmntInd>")
            content += make_line("  </MndtRltdInf>")
            content += make_line("  <CdtrSchmeId>")
            content += make_line("    <Id>")
            content += make_line("      <PrvtId>")
            content += make_line("        <Othr>")
            content += make_line("          <Id>{0}-{1}</Id>".format(self.name, transaction_count))
            content += make_line("          <SchmeNm>")
            content += make_line("            <Prtry>SEPA</Prtry>")
            content += make_line("          </SchmeNm>")
            content += make_line("        </Othr>")
            content += make_line("      </PrvtId>")
            content += make_line("    </Id>")
            content += make_line("  </CdtrSchmeId>")
            content += make_line("</DrctDbtTx>")
            content += make_line("<DbtrAgt>")
            content += make_line("  <FinInstnId>")
            content += make_line("    <BIC>{0}</BIC>".format(customer.bic))
            content += make_line("  </FinInstnId>")
            content += make_line("</DbtrAgt>")
            content += make_line("<Dbtr>")
            content += make_line("  <Nm>{0}</Nm>".format(customer.full_name))
            content += make_line("</Dbtr>")
            content += make_line("<DbtrAcct>")
            content += make_line("  <Id>")
            content += make_line("    <IBAN>{0}</IBAN>".format(customer.iban))
            content += make_line("  </Id>")
            content += make_line("</DbtrAcct>")
            content += make_line("<RmtInf>")
            content += make_line("  <Ustrd>{0}</Ustrd>".format(payment.reference))
            content += make_line("</RmtInf>")
            content += make_line("</DrctDbtTxInf>")
      
        # add footer
        content += make_line("    </PmtInf>")
        content += make_line("  </CstmrDrctDbtInitn>")
        content += make_line("</Document>")
        # insert control numbers
        content = content.replace(transaction_count_identifier, "{0}".format(transaction_count))
        content = content.replace(control_sum_identifier, "{:.2f}".format(control_sum))
        
        return { 'content': content }
    pass

def get_company_name(sales_invoice):
    return frappe.get_value('Sales Invoice', sales_invoice, 'company')
    
# this function will create a new direct debit proposal
@frappe.whitelist()
def create_direct_debit_proposal():
    # get all customers with open sales invoices
    sql_query = ("""SELECT `customer`, `name`,  `outstanding_amount`, `due_date`
            FROM `tabSales Invoice` 
            WHERE `docstatus` = 1 
              AND `outstanding_amount` > 0
              AND `enable_lsv` = 1
              AND `is_proposed` = 0;""")
    sales_invoices = frappe.db.sql(sql_query, as_dict=True)
    new_record = None
    # get all sales invoices that are overdue
    if sales_invoices:
        now = datetime.now()
        invoices = []
        for invoice in sales_invoices:
            new_invoice = { 
                'customer': invoice.customer,
                'sales_invoice': invoice.name,
                'amount': invoice.outstanding_amount,
                'due_date': invoice.due_date
            }
            invoices.append(new_invoice)
        # create new record
        new_proposal = frappe.get_doc({
            "doctype": "Direct Debit Proposal",
            "title": "{year:04d}-{month:02d}-{day:02d}".format(year=now.year, month=now.month, day=now.day),
            "date": "{year:04d}-{month:02d}-{day:02d}".format(year=now.year, month=now.month, day=now.day),
            "sales_invoices": invoices
        })
        proposal_record = new_proposal.insert()
        new_record = proposal_record.name
        frappe.db.commit()
    return new_record