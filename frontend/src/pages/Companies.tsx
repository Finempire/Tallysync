import { useState } from 'react'
import { Card, Table, Button, Modal, Form, Input, message, Tag, Space, Typography, Popconfirm, Spin, Alert } from 'antd'
import { PlusOutlined, EditOutlined, SyncOutlined, DeleteOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { companiesApi, tallyApi } from '../api/client'

const { Title } = Typography

export default function Companies() {
  const [modalOpen, setModalOpen] = useState(false)
  const [editingCompany, setEditingCompany] = useState<any>(null)
  const [form] = Form.useForm()
  const queryClient = useQueryClient()

  // Get Tally companies (actually connected ones)
  const { data: tallyCompanies, isLoading: loadingTally, error: tallyError } = useQuery({
    queryKey: ['tallyCompanies'],
    queryFn: tallyApi.getCompanies
  })

  // Get database companies
  const { data: companies, isLoading } = useQuery({ queryKey: ['companies'], queryFn: companiesApi.list })

  const createMutation = useMutation({
    mutationFn: (data: any) => editingCompany ? companiesApi.update(editingCompany.id, data) : companiesApi.create(data),
    onSuccess: () => { message.success(editingCompany ? 'Company updated!' : 'Company created!'); setModalOpen(false); setEditingCompany(null); form.resetFields(); queryClient.invalidateQueries({ queryKey: ['companies'] }) }
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => companiesApi.delete(id),
    onSuccess: () => { message.success('Company deleted!'); queryClient.invalidateQueries({ queryKey: ['companies'] }) }
  })

  const syncLedgersMutation = useMutation({
    mutationFn: (companyName: string) => tallyApi.syncLedgers(companyName),
    onSuccess: () => { message.success('Ledgers synced successfully!'); queryClient.invalidateQueries({ queryKey: ['companies'] }) },
    onError: () => { message.error('Failed to sync ledgers') }
  })

  // Combine Tally companies with database companies
  const rawTallyList = tallyCompanies?.data?.companies || tallyCompanies?.data || []
  const dbCompanyList = companies?.data?.results || companies?.data || []

  // Create merged list - prioritize Tally companies
  // Handle both cases: tallyItem could be a string or an object with name property
  const mergedCompanies = rawTallyList.map((tallyItem: any, index: number) => {
    const tallyName = typeof tallyItem === 'string' ? tallyItem : tallyItem?.name || tallyItem
    const dbMatch = dbCompanyList.find((c: any) => c.name === tallyName || c.tally_company === tallyName)
    return {
      id: dbMatch?.id || `tally-${index}`,
      name: String(tallyName),
      gstin: dbMatch?.gstin || '-',
      pan: dbMatch?.pan || '-',
      tally_connected: true,
      last_tally_sync: dbMatch?.last_tally_sync,
      isFromTally: true
    }
  })

  // Add any database companies not in Tally list
  dbCompanyList.forEach((dbCompany: any) => {
    if (!mergedCompanies.find((c: any) => c.name === dbCompany.name)) {
      mergedCompanies.push({
        ...dbCompany,
        tally_connected: false,
        isFromTally: false
      })
    }
  })

  const columns = [
    {
      title: 'Name', dataIndex: 'name', key: 'name', render: (name: string, r: any) => (
        <Space>
          {name}
          {r.isFromTally && <Tag color="green" icon={<CheckCircleOutlined />}>Tally</Tag>}
        </Space>
      )
    },
    { title: 'GSTIN', dataIndex: 'gstin', key: 'gstin' },
    { title: 'PAN', dataIndex: 'pan', key: 'pan' },
    { title: 'Tally', dataIndex: 'tally_connected', key: 'tally', render: (connected: boolean) => <Tag color={connected ? 'green' : 'default'}>{connected ? 'Connected' : 'Not Connected'}</Tag> },
    { title: 'Last Sync', dataIndex: 'last_tally_sync', key: 'lastSync', render: (d: string) => d ? new Date(d).toLocaleString() : '-' },
    {
      title: 'Actions', key: 'actions', render: (_: any, r: any) => (
        <Space>
          {typeof r.id === 'number' && (
            <Button size="small" icon={<EditOutlined />} onClick={() => { setEditingCompany(r); form.setFieldsValue(r); setModalOpen(true) }}>Edit</Button>
          )}
          <Button
            size="small"
            icon={<SyncOutlined spin={syncLedgersMutation.isPending} />}
            onClick={() => syncLedgersMutation.mutate(r.name)}
            disabled={!r.isFromTally || syncLedgersMutation.isPending}
          >
            Sync Ledgers
          </Button>
          {typeof r.id === 'number' && (
            <Popconfirm title="Delete this company?" onConfirm={() => deleteMutation.mutate(r.id)} okText="Yes" cancelText="No">
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      )
    }
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>Companies</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingCompany(null); form.resetFields(); setModalOpen(true) }}>Add Company</Button>
      </div>

      {tallyError && (
        <Alert
          message="Tally Connection Issue"
          description="Could not connect to Tally. Make sure Tally is running with the company open."
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Card>
        <Table
          dataSource={mergedCompanies}
          columns={columns}
          loading={isLoading || loadingTally}
          rowKey="id"
          locale={{ emptyText: loadingTally ? <Spin /> : 'No companies found. Connect to Tally or add a company.' }}
        />
      </Card>

      <Modal title={editingCompany ? 'Edit Company' : 'Add Company'} open={modalOpen} onCancel={() => setModalOpen(false)} footer={null}>
        <Form form={form} layout="vertical" onFinish={(values) => createMutation.mutate(values)}>
          <Form.Item name="name" label="Company Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="gstin" label="GSTIN" rules={[{ pattern: /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/, message: 'Invalid GSTIN' }]}><Input placeholder="29AABCU9603R1ZM" /></Form.Item>
          <Form.Item name="pan" label="PAN" rules={[{ pattern: /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/, message: 'Invalid PAN' }]}><Input placeholder="ABCDE1234F" /></Form.Item>
          <Form.Item name="address_line1" label="Address"><Input /></Form.Item>
          <div style={{ display: 'flex', gap: 16 }}>
            <Form.Item name="city" label="City" style={{ flex: 1 }}><Input /></Form.Item>
            <Form.Item name="state" label="State" style={{ flex: 1 }}><Input /></Form.Item>
            <Form.Item name="pincode" label="Pincode" style={{ flex: 1 }}><Input /></Form.Item>
          </div>
          <Form.Item><Button type="primary" htmlType="submit" loading={createMutation.isPending} block>{editingCompany ? 'Update' : 'Create'}</Button></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
