import { useState } from 'react'
import { Card, Tabs, Table, Button, Tag, Space, Typography, Statistic, Row, Col, DatePicker, Modal, message } from 'antd'
import { FileTextOutlined, CheckCircleOutlined, SyncOutlined, DownloadOutlined } from '@ant-design/icons'
import { useQuery, useMutation } from '@tanstack/react-query'
import { gstApi } from '../api/client'
import dayjs from 'dayjs'

const { Title } = Typography

export default function GSTCompliance() {
  const [selectedPeriod, setSelectedPeriod] = useState(dayjs().subtract(1, 'month').format('MMYYYY'))

  const { data: einvoices } = useQuery({ queryKey: ['einvoices'], queryFn: gstApi.listEInvoices })
  const { data: gstr1Summary } = useQuery({ queryKey: ['gstr1-summary', selectedPeriod], queryFn: () => gstApi.getGSTR1Summary(1, selectedPeriod) })

  const generateMutation = useMutation({
    mutationFn: (id: number) => gstApi.generateEInvoice(id),
    onSuccess: () => message.success('E-Invoice generated successfully!')
  })

  const einvoiceColumns = [
    { title: 'Invoice No', dataIndex: 'doc_number', key: 'docNumber' },
    { title: 'Date', dataIndex: 'doc_date', key: 'date' },
    { title: 'Buyer', dataIndex: 'buyer_name', key: 'buyer' },
    { title: 'Buyer GSTIN', dataIndex: 'buyer_gstin', key: 'buyerGstin' },
    { title: 'Total Value', dataIndex: 'total_invoice_value', key: 'value', render: (v: number) => `₹${v?.toLocaleString()}` },
    { title: 'IRN', dataIndex: 'irn', key: 'irn', render: (irn: string) => irn ? <span style={{ fontSize: 10 }}>{irn.substring(0, 20)}...</span> : '-' },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={{ draft: 'default', pending: 'orange', generated: 'green', cancelled: 'red', failed: 'red' }[s]}>{s}</Tag> },
    { title: 'Actions', key: 'actions', render: (_: any, r: any) => (
      <Space>
        {r.status === 'draft' && <Button size="small" type="primary" onClick={() => generateMutation.mutate(r.id)}>Generate</Button>}
        {r.status === 'generated' && <Button size="small" icon={<DownloadOutlined />}>QR Code</Button>}
      </Space>
    )}
  ]

  return (
    <div>
      <Title level={4}>GST Compliance</Title>
      
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={6}><Card><Statistic title="E-Invoices Generated" value={einvoices?.data?.filter((e: any) => e.status === 'generated').length || 0} prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />} /></Card></Col>
        <Col xs={24} sm={12} lg={6}><Card><Statistic title="Pending E-Invoices" value={einvoices?.data?.filter((e: any) => e.status === 'draft').length || 0} prefix={<FileTextOutlined style={{ color: '#faad14' }} />} /></Card></Col>
        <Col xs={24} sm={12} lg={6}><Card><Statistic title="GSTR-1 Status" value="Filed" prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />} /></Card></Col>
        <Col xs={24} sm={12} lg={6}><Card><Statistic title="GSTR-3B Status" value="Due" prefix={<SyncOutlined style={{ color: '#1890ff' }} />} /></Card></Col>
      </Row>

      <Card>
        <Tabs defaultActiveKey="einvoice" items={[
          { key: 'einvoice', label: 'E-Invoicing', children: (
            <div>
              <div style={{ marginBottom: 16 }}><Button type="primary" icon={<FileTextOutlined />}>Create E-Invoice</Button></div>
              <Table dataSource={einvoices?.data || []} columns={einvoiceColumns} rowKey="id" />
            </div>
          )},
          { key: 'gstr1', label: 'GSTR-1', children: (
            <div>
              <div style={{ marginBottom: 16 }}>
                <Space>
                  <DatePicker picker="month" value={dayjs(selectedPeriod, 'MMYYYY')} onChange={(d) => d && setSelectedPeriod(d.format('MMYYYY'))} />
                  <Button type="primary">Prepare GSTR-1</Button>
                  <Button icon={<DownloadOutlined />}>Download JSON</Button>
                </Space>
              </div>
              <Row gutter={16}>
                <Col span={8}><Statistic title="B2B Invoices" value={gstr1Summary?.data?.b2b_count || 0} /></Col>
                <Col span={8}><Statistic title="B2C Invoices" value={gstr1Summary?.data?.b2c_count || 0} /></Col>
                <Col span={8}><Statistic title="Total Taxable" value={gstr1Summary?.data?.total_taxable || 0} prefix="₹" /></Col>
              </Row>
            </div>
          )},
          { key: 'gstr3b', label: 'GSTR-3B', children: (
            <div>
              <div style={{ marginBottom: 16 }}><Button type="primary">Compute GSTR-3B</Button></div>
              <Card title="Tax Liability Summary">
                <Row gutter={16}>
                  <Col span={6}><Statistic title="IGST" value={0} prefix="₹" /></Col>
                  <Col span={6}><Statistic title="CGST" value={0} prefix="₹" /></Col>
                  <Col span={6}><Statistic title="SGST" value={0} prefix="₹" /></Col>
                  <Col span={6}><Statistic title="Total Payable" value={0} prefix="₹" valueStyle={{ color: '#cf1322' }} /></Col>
                </Row>
              </Card>
            </div>
          )},
          { key: 'reconciliation', label: 'Reconciliation', children: (
            <div>
              <div style={{ marginBottom: 16 }}><Button type="primary">Reconcile GSTR-2B</Button></div>
              <Table columns={[
                { title: 'Supplier GSTIN', dataIndex: 'supplier_gstin' },
                { title: 'Invoice No', dataIndex: 'invoice_number' },
                { title: 'Invoice Date', dataIndex: 'invoice_date' },
                { title: 'Taxable Value', dataIndex: 'taxable_value' },
                { title: 'Match Status', dataIndex: 'match_type', render: (t: string) => <Tag color={t === 'exact' ? 'green' : t === 'mismatch' ? 'red' : 'orange'}>{t}</Tag> },
              ]} dataSource={[]} />
            </div>
          )},
          { key: 'ewaybill', label: 'E-Way Bill', children: (
            <div>
              <div style={{ marginBottom: 16 }}><Button type="primary">Generate E-Way Bill</Button></div>
              <Table columns={[
                { title: 'EWB No', dataIndex: 'ewb_number' },
                { title: 'Date', dataIndex: 'ewb_date' },
                { title: 'Document', dataIndex: 'doc_number' },
                { title: 'To State', dataIndex: 'to_state_code' },
                { title: 'Value', dataIndex: 'total_value' },
                { title: 'Valid Till', dataIndex: 'ewb_valid_till' },
                { title: 'Status', dataIndex: 'status', render: (s: string) => <Tag color={s === 'generated' ? 'green' : 'default'}>{s}</Tag> },
              ]} dataSource={[]} />
            </div>
          )}
        ]} />
      </Card>
    </div>
  )
}
