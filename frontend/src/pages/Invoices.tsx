import { useState } from 'react'
import { Card, Table, Button, Upload, Modal, Form, Select, message, Tag, Space, Typography, Image, Descriptions, Progress } from 'antd'
import { UploadOutlined, EyeOutlined, CheckOutlined, FileImageOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { invoicesApi, companiesApi } from '../api/client'

const { Title } = Typography

export default function Invoices() {
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [previewInvoice, setPreviewInvoice] = useState<any>(null)
  const queryClient = useQueryClient()

  const { data: invoices, isLoading } = useQuery({ queryKey: ['invoices'], queryFn: () => invoicesApi.list() })
  const { data: companies } = useQuery({ queryKey: ['companies'], queryFn: companiesApi.list })

  const uploadMutation = useMutation({
    mutationFn: (formData: FormData) => invoicesApi.upload(formData),
    onSuccess: () => { message.success('Invoice uploaded and processed!'); setUploadModalOpen(false); queryClient.invalidateQueries({ queryKey: ['invoices'] }) }
  })

  const approveMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => invoicesApi.approve(id, data),
    onSuccess: () => { message.success('Invoice approved!'); queryClient.invalidateQueries({ queryKey: ['invoices'] }) }
  })

  const columns = [
    { title: 'Vendor', dataIndex: 'vendor_name', key: 'vendor' },
    { title: 'Invoice No', dataIndex: 'invoice_number', key: 'invoiceNo' },
    { title: 'Date', dataIndex: 'invoice_date', key: 'date' },
    { title: 'Amount', dataIndex: 'total_amount', key: 'amount', render: (a: number) => `₹${a?.toLocaleString()}` },
    { title: 'GST', key: 'gst', render: (_: any, r: any) => `₹${((r.cgst_amount || 0) + (r.sgst_amount || 0) + (r.igst_amount || 0)).toLocaleString()}` },
    { title: 'OCR Confidence', dataIndex: 'ocr_confidence', key: 'confidence', render: (c: number) => <Progress percent={Math.round((c || 0) * 100)} size="small" style={{ width: 80 }} /> },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={{ uploaded: 'default', processing: 'blue', extracted: 'cyan', validated: 'orange', approved: 'green', voucher_created: 'green', failed: 'red' }[s]}>{s}</Tag> },
    {
      title: 'Actions', key: 'actions', render: (_: any, r: any) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => setPreviewInvoice(r)}>View</Button>
          {r.status === 'extracted' && <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => approveMutation.mutate({ id: r.id, data: {} })}>Approve</Button>}
        </Space>
      )
    }
  ]

  const handleUpload = (values: any) => {
    const formData = new FormData()
    formData.append('company', values.company)
    formData.append('invoice_type', values.invoice_type || 'purchase')
    formData.append('file', values.file.file)
    uploadMutation.mutate(formData)
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>Invoice OCR</Title>
        <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadModalOpen(true)}>Upload Invoice</Button>
      </div>
      <Card>
        <Table dataSource={invoices?.data?.results || invoices?.data || []} columns={columns} loading={isLoading} rowKey="id" />
      </Card>

      <Modal title="Upload Invoice" open={uploadModalOpen} onCancel={() => setUploadModalOpen(false)} footer={null}>
        <Form layout="vertical" onFinish={handleUpload}>
          <Form.Item name="company" label="Company" rules={[{ required: true }]}>
            <Select placeholder="Select company">{(companies?.data?.results || companies?.data || []).map((c: any) => <Select.Option key={c.id} value={c.id}>{c.name}</Select.Option>)}</Select>
          </Form.Item>
          <Form.Item name="invoice_type" label="Invoice Type" initialValue="purchase">
            <Select>
              <Select.Option value="purchase">Purchase Invoice</Select.Option>
              <Select.Option value="expense">Expense Invoice</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="file" label="Invoice File" rules={[{ required: true }]}>
            <Upload beforeUpload={() => false} accept=".pdf,.jpg,.jpeg,.png" maxCount={1}>
              <Button icon={<UploadOutlined />}>Select File</Button>
            </Upload>
          </Form.Item>
          <Form.Item><Button type="primary" htmlType="submit" loading={uploadMutation.isPending} block>Upload & Process OCR</Button></Form.Item>
        </Form>
      </Modal>

      <Modal title="Invoice Details" open={!!previewInvoice} onCancel={() => setPreviewInvoice(null)} width={800} footer={null}>
        {previewInvoice && (
          <div style={{ display: 'flex', gap: 24 }}>
            <div style={{ flex: 1 }}>
              <Card title="Extracted Data">
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="Vendor">{previewInvoice.vendor_name}</Descriptions.Item>
                  <Descriptions.Item label="GSTIN">{previewInvoice.vendor_gstin}</Descriptions.Item>
                  <Descriptions.Item label="Invoice No">{previewInvoice.invoice_number}</Descriptions.Item>
                  <Descriptions.Item label="Date">{previewInvoice.invoice_date}</Descriptions.Item>
                  <Descriptions.Item label="Subtotal">₹{previewInvoice.subtotal?.toLocaleString()}</Descriptions.Item>
                  <Descriptions.Item label="CGST">₹{previewInvoice.cgst_amount?.toLocaleString()}</Descriptions.Item>
                  <Descriptions.Item label="SGST">₹{previewInvoice.sgst_amount?.toLocaleString()}</Descriptions.Item>
                  <Descriptions.Item label="IGST">₹{previewInvoice.igst_amount?.toLocaleString()}</Descriptions.Item>
                  <Descriptions.Item label="Total">₹{previewInvoice.total_amount?.toLocaleString()}</Descriptions.Item>
                </Descriptions>
              </Card>
            </div>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f5f5f5', borderRadius: 8, minHeight: 300 }}>
              <FileImageOutlined style={{ fontSize: 64, color: '#ccc' }} />
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
